My Aave V2 Wallet Credit Score Project: Understanding DeFi Behavior

Hey there! I'm really excited to share this project where I built a system to give Aave V2 wallets a "credit score" from 0 to 1000. It's all about figuring out who's a reliable user and who might be a bit risky, just by looking at their past transactions.

The Big Idea

The challenge was to assign a score to each wallet based only on its transaction history with Aave V2. Think of it like a credit score, but for crypto wallets! Higher scores mean responsible usage, lower scores might point to risky or bot-like behavior.

How I Built It (My "Model")

Since I didn't have a pre-labeled list of "good" or "bad" wallets, I went with a rule-based scoring system. This means I set up clear rules that add or subtract points based on a wallet's actions. It's super transparent – you can see exactly why a wallet got its score!

What I Looked At (Key Features)

I dug into the user-wallet-transactions.json file and focused on a few key things for each wallet:
Deposits & Repays: How much money they put in and how much they paid back.

Borrows: How much they borrowed.

Liquidations: This is a big one! How many times their position was liquidated (a sign of trouble).

Repay-to-Borrow Ratio: Did they pay back what they borrowed? This is crucial.

Activity Time: How long they've been active.

How the Score is Calculated
Every wallet starts with a neutral score (500 points). Then, points are adjusted:
You Gain Points For:
Making deposits.
Repaying your borrows on time (especially fully!).
Being active for a long period.

You Lose Points For:
Getting liquidated (this is a major hit!).
Not repaying your borrows adequately.
Borrowing heavily without enough deposits or proper repayment.
The final score is then capped between 0 and 1000.

How to Run My Code

It's a simple Python script (generate_wallet_scores.py):

Save the Python code (from the previous response) as generate_wallet_scores.py.

Make sure user-wallet-transactions.json is in the same folder.

Open your terminal and run:

python generate_wallet_scores.py

It'll show you the scores and save them to wallet_credit_scores.json.

What's Next?

This was a really fun project! If I had more time (or more data!), I'd love to explore:
Using more advanced machine learning to learn the best scoring rules automatically.

Looking at transaction timing patterns more deeply.

Building a cool visual dashboard for the scores!

Thanks for checking it out!

