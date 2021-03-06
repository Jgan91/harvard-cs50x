from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import mkdtemp

import sys

from helpers import *

# configure application
app = Flask(__name__)

# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# custom filter
app.jinja_env.filters["usd"] = usd

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

@app.route("/")
@login_required
def index():
    # retrieve portfolio if not first time registering
    stocks, cash, total = portfolio()

    # display portfolio
    return render_template("index.html", stocks=stocks, cash=usd(cash), total=usd(total))

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock."""
    if request.method == "POST":
        # retrieve stock quote
        try:
            name, price, symbol = get_quote(request.form.get("symbol"))
        except (ValueError, TypeError):
            return apology("invalid stock")

        # ensure numeric input
        shares = int(request.form.get("shares"))
        if shares == "":
            return apology("missing shares")
        elif not request.form.get("shares").isnumeric():
            return apology("invalid shares")
        cost = shares * price

        # check if user can afford stocks
        cash = db.execute("SELECT cash FROM users WHERE user_id = :id_",
            id_=session["user_id"])[0]["cash"]
        if cost > cash:
            return apology("can't afford")

        # add stock to user's portfolio
        else:
            # check for stock in database
            symbol_id = db.execute("SELECT symbol_id FROM stocks WHERE symbol = :symbol",
                symbol=symbol)

            # add stock to database if it doesn't exist
            if len(symbol_id) == 0:
                db.execute("INSERT INTO stocks (symbol, name) VALUES (:symbol, :name)",
                    symbol=symbol, name=name)
                symbol_id = db.execute("SELECT symbol_id FROM stocks WHERE symbol = :symbol",
                    symbol=symbol)

            # compute current time
            time = db.execute("SELECT datetime('now')")[0]["datetime('now')"]

            # insert transaction into database
            db.execute("INSERT INTO transactions (user_id, symbol_id, shares, price, time) VALUES (:user_id, :symbol_id, :shares, :price, :time)",
                user_id=session["user_id"], symbol_id=symbol_id[0]["symbol_id"], shares=shares, price=price, time=time)

        # update cash
        db.execute("UPDATE users SET cash = cash - :cost WHERE user_id = :id_", cost=cost, id_=session["user_id"])

        # redirect user to homepage
        flash('Bought!')
        return redirect(url_for("index"))


    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        # retrieve portfolio
        stocks, cash, total = portfolio()

        # display form
        return render_template("buy.html", stocks=stocks, cash=usd(cash), total=usd(total))

def get_quote(symbol):
    # retrieve stock quote
    stock = lookup(symbol)

    # ensure stock is valid
    if stock == None:
        return

    # store stock info
    name = stock["name"]
    price = stock["price"]
    symbol = stock["symbol"]

    return name, price, symbol

@app.route("/history")
@login_required
def history():
    """Show history of transactions."""
    # retrieve transaction history
    transactions = db.execute("SELECT * FROM users JOIN transactions ON users.user_id = transactions.user_id JOIN stocks ON transactions.symbol_id = stocks.symbol_id WHERE users.user_id = :user_id ORDER BY transactions.time",
        user_id=session["user_id"])

    return render_template("history.html", transactions=transactions)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        # ensure username exists and password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["hash"]):
            return apology("invalid username and/or password")

        # remember which user has registered
        session["user_id"] = rows[0]["user_id"]

        # redirect user to home page
        flash("Welcome, {}".format(rows[0]["username"]))
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out."""

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("login"))

def portfolio():
    """Retrieve users portfolio"""
    # store symbol, name, shares, total
    #try:
    stocks = db.execute("SELECT symbol, name, sum(shares) FROM transactions JOIN stocks ON transactions.symbol_id = stocks.symbol_id WHERE transactions.user_id = :user_id GROUP BY stocks.symbol_id", user_id=session["user_id"])
    total = 0

    # iterate over each stock to find current price & holding value
    for stock in stocks:
        price = lookup(stock["symbol"])["price"]
        stock["price"] = usd(price)
        holding = price * stock["sum(shares)"]
        stock["total"] = usd(holding)
        total += holding

    # retrieve user's cash amount
    cash = db.execute("SELECT cash FROM users WHERE user_id = :user_id",
        user_id=session["user_id"])[0]["cash"]
    total += cash
    return stocks, cash, total
'''
    except:
        stocks = []
        cash = 10000
        total = 10000
        return stocks, cash, total
'''

@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    # retrieve portfolio
    stocks, cash, total = portfolio()

    if request.method == "POST":

        # retrieve stock quote
        try:
            name, price, symbol = get_quote(request.form.get("symbol"))
        except (ValueError, TypeError):
            return apology("invalid stock")

        # display stock quote
        return render_template("quoted.html", name=name, price=usd(price), symbol=symbol, stocks=stocks, cash=usd(cash), total=usd(total))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        # display form
        return render_template("quote.html", stocks=stocks, cash=usd(cash), total=usd(total))

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user."""
    if request.method == "POST":

        # ensure user inputs username
        username = request.form.get("username")
        password = request.form.get("password")
        confirm = request.form.get("confirm")

        if not username:
            return apology("Missing username!")

        # ensure user inputs the same password twice
        elif not password:
            return apology("Missing password!")

        elif not confirm:
            return apology("Please confirm password!")

        elif password != confirm:
            return apology("Passwords don't match! Please try again.")

        # query database
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=username)

        # ensure username doesn't exist
        if len(rows) == 1:
            return apology("username already exists")

        # INSERT new user into users, storing a hash of their password
        else:
            hash_ = pwd_context.hash(request.form.get("password"))
            rows = db.execute("INSERT INTO users (username, hash) VALUES(:username, :hash_)",
                username=request.form.get("username"), hash_=hash_)
            session["user_id"] = db.execute("SELECT user_id FROM users WHERE username = :username", username=username)[0]["user_id"]
            flash("Registered! Welcome {}".format(username))
            return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock."""
    # retrieve portfolio
    stocks, cash, total = portfolio()

    if request.method == "POST":
        # remove stock from user's portfolio
        # check if user has the shares they want to sell
        sell = int(request.form.get("shares"))
        shares = db.execute("SELECT sum(shares) FROM transactions JOIN stocks ON transactions.symbol_id = stocks.symbol_id WHERE user_id = :user_id AND symbol = :symbol GROUP BY user_id",
        user_id=session["user_id"], symbol=request.form.get("symbol").upper())
        if len(shares) == 0 or sell > shares[0]["sum(shares)"]:
            return apology("you have not enough minerals")

        # implement sale as negative quantity transaction
        else:
            # retrieve stock quote
            try:
                name, price, symbol = get_quote(request.form.get("symbol"))
            except (ValueError, TypeError):
                return apology("invalid stock")

            # retrieve symbol_id
            symbol_id = db.execute("SELECT symbol_id FROM stocks WHERE symbol = :symbol",
                    symbol=symbol)

            # compute current time
            time = db.execute("SELECT datetime('now')")[0]["datetime('now')"]

            db.execute("INSERT INTO transactions (user_id, symbol_id, shares, price, time) VALUES (:user_id, :symbol_id, :shares, :price, :time)",
            user_id=session["user_id"], symbol_id=symbol_id[0]["symbol_id"], shares=-sell, price=price, time=time)

            # update cash
            cost = price * sell
            db.execute("UPDATE users SET cash = cash + :cost WHERE user_id = :id_", cost=cost, id_=session["user_id"])

            # redirect to index
            flash("Sold!")
            return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        # display form
        return render_template("sell.html", stocks=stocks, cash=usd(cash), total=usd(total))


