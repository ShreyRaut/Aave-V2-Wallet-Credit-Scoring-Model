import json
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, getcontext

# Set precision for Decimal calculations to avoid floating-point issues with financial data
getcontext().prec = 30 # High precision for DeFi amounts

def generate_wallet_scores(transaction_data_path="user-wallet-transactions.json"):
    """
    Calculates a credit score (0-1000) for each Aave V2 wallet based on its transaction history.
    This function implements a rule-based model to assess wallet behavior.

    Args:
        transaction_data_path (str): The file path to the JSON containing raw transaction data.

    Returns:
        dict: A dictionary mapping wallet addresses (str) to their calculated credit scores (int).
    """
    print(f"Starting the wallet credit scoring process using data from: {transaction_data_path}")

    # Initialize a dictionary to hold aggregated features for each unique wallet.
    # Using defaultdict simplifies adding new wallets and their initial feature sets.
    wallet_activity_summary = defaultdict(lambda: {
        'deposit_count': 0,
        'borrow_count': 0,
        'repay_count': 0,
        'redeem_underlying_count': 0,
        'liquidation_call_count': 0, # Crucial for identifying risky behavior
        'total_deposited_usd': Decimal('0.0'),
        'total_borrowed_usd': Decimal('0.0'),
        'total_repaid_usd': Decimal('0.0'),
        'first_transaction_timestamp': float('inf'), # Tracks the earliest activity
        'last_transaction_timestamp': float('-inf'),  # Tracks the most recent activity
    })

    try:
        with open(transaction_data_path, 'r') as f:
            raw_transactions = json.load(f)
        print(f"Successfully loaded {len(raw_transactions)} transactions.")
    except FileNotFoundError:
        print(f"Error: The transaction data file was not found at '{transaction_data_path}'. Please ensure it's in the correct directory.")
        return {}
    except json.JSONDecodeError:
        print(f"Error: Failed to parse JSON from '{transaction_data_path}'. Check if the file is valid JSON.")
        return {}
    except Exception as e:
        print(f"An unexpected error occurred while loading the file: {e}")
        return {}

    # --- Feature Engineering Phase ---
    # Iterate through each transaction to build a comprehensive summary for every wallet.
    # This is where we extract raw data into meaningful features.
    for i, transaction_record in enumerate(raw_transactions):
        if (i + 1) % 10000 == 0: # Provide a progress update for larger datasets
            print(f"Processing transaction {i + 1} of {len(raw_transactions)}...")

        wallet_address = transaction_record.get('userWallet')
        action_type = transaction_record.get('action')
        transaction_timestamp = transaction_record.get('timestamp')
        action_details = transaction_record.get('actionData', {})
        amount_str = action_details.get('amount')
        asset_price_usd_str = action_details.get('assetPriceUSD')

        # Basic validation: ensure essential fields are present
        if not all([wallet_address, action_type, transaction_timestamp is not None, amount_str, asset_price_usd_str]):
            # print(f"Skipping incomplete transaction record: {transaction_record.get('txHash', 'N/A')}")
            continue

        try:
            # Convert amounts and prices to Decimal for precise financial calculations.
            # This is crucial to avoid floating-point inaccuracies.
            amount = Decimal(amount_str)
            asset_price_usd = Decimal(asset_price_usd_str)
            usd_value = amount * asset_price_usd
        except Exception as e:
            print(f"Warning: Could not convert financial values for transaction {transaction_record.get('txHash', 'N/A')}. Skipping. Error: {e}")
            continue

        # Update wallet's overall activity timestamps
        wallet_activity_summary[wallet_address]['first_transaction_timestamp'] = min(
            wallet_activity_summary[wallet_address]['first_transaction_timestamp'], transaction_timestamp
        )
        wallet_activity_summary[wallet_address]['last_transaction_timestamp'] = max(
            wallet_activity_summary[wallet_address]['last_transaction_timestamp'], transaction_timestamp
        )

        # Aggregate counts and USD volumes based on the transaction action type
        if action_type == 'deposit':
            wallet_activity_summary[wallet_address]['deposit_count'] += 1
            wallet_activity_summary[wallet_address]['total_deposited_usd'] += usd_value
        elif action_type == 'borrow':
            wallet_activity_summary[wallet_address]['borrow_count'] += 1
            wallet_activity_summary[wallet_address]['total_borrowed_usd'] += usd_value
        elif action_type == 'repay':
            wallet_activity_summary[wallet_address]['repay_count'] += 1
            wallet_activity_summary[wallet_address]['total_repaid_usd'] += usd_value
        elif action_type == 'redeemunderlying':
            wallet_activity_summary[wallet_address]['redeem_underlying_count'] += 1
        elif action_type == 'liquidationcall':
            wallet_activity_summary[wallet_address]['liquidation_call_count'] += 1
            # Liquidations are a strong negative signal, so we track them explicitly.

    print("Feature engineering complete. Starting score calculation...")

    # --- Credit Score Calculation Phase ---
    # Iterate through the aggregated wallet data and apply the scoring logic.
    final_wallet_scores = {}
    for wallet_address, features in wallet_activity_summary.items():
        # Start with a neutral base score. This allows for both positive and negative adjustments.
        current_score = 500

        # Calculate key derived metrics for scoring
        repay_to_borrow_ratio = Decimal('0.0')
        if features['total_borrowed_usd'] > Decimal('0.0'):
            repay_to_borrow_ratio = features['total_repaid_usd'] / features['total_borrowed_usd']
        elif features['borrow_count'] == 0:
            # If a wallet never borrowed, its repayment ratio is effectively perfect.
            repay_to_borrow_ratio = Decimal('1.0')

        # --- Positive Contributions: Rewarding responsible and active behavior ---

        # 1. Deposits: Wallets that deposit more value are generally more engaged and provide liquidity.
        # Capped to prevent a single massive deposit from disproportionately inflating the score.
        # Every $1000 deposited (up to $200,000) adds 1 point.
        current_score += min(int(features['total_deposited_usd'] / Decimal('1000')), 200)

        # 2. Repayment Behavior: This is a cornerstone of creditworthiness.
        # Higher repayment ratios indicate reliability.
        if repay_to_borrow_ratio >= Decimal('1.0'): # Fully repaid or overpaid
            current_score += 150
        elif repay_to_borrow_ratio > Decimal('0.75'): # Strong repayment
            current_score += 75
        elif repay_to_borrow_ratio > Decimal('0.5'): # Moderate repayment
            current_score += 25

        # 3. Sustained Activity: Longer-term engagement suggests a more stable user.
        if features['last_transaction_timestamp'] > 0 and features['first_transaction_timestamp'] < float('inf'):
            activity_duration_days = (features['last_transaction_timestamp'] - features['first_transaction_timestamp']) / (60 * 60 * 24)
            if activity_duration_days > 365: # Active for over a year
                current_score += 20
            elif activity_duration_days > 180: # Active for over 6 months
                current_score += 10

        # --- Negative Contributions: Penalizing risky or problematic behavior ---

        # 1. Liquidations: The most significant negative signal. Each liquidation indicates a failure to manage collateral.
        current_score -= features['liquidation_call_count'] * 200 # Heavy penalty per liquidation

        # 2. Poor Repayment Ratio: If a wallet borrowed and failed to repay a significant portion.
        if features['total_borrowed_usd'] > Decimal('0.0') and repay_to_borrow_ratio < Decimal('0.5'):
            current_score -= 100 # Substantial deduction for low repayment

        # 3. High Leverage/Unbalanced Borrowing: Wallets borrowing heavily relative to their deposits,
        # especially if repayment isn't strong, might be deemed riskier.
        if (features['borrow_count'] > 0 and
            features['total_borrowed_usd'] > features['total_deposited_usd'] * Decimal('0.75')):
            # If borrowed amount is more than 75% of deposited amount AND
            # (repayment is low OR borrows significantly outnumber repays)
            if repay_to_borrow_ratio < Decimal('0.75') or features['borrow_count'] > features['repay_count'] * 1.5:
                current_score -= 75 # Deduction for potentially risky leverage/behavior

        # Final step: Ensure the score is within the 0-1000 bounds
        final_wallet_scores[wallet_address] = max(0, min(1000, int(current_score)))

    print("Score calculation complete.")
    return final_wallet_scores

if __name__ == "__main__":
    # This block executes when the script is run directly.
    # It's set up to process the provided JSON file and output the results.
    calculated_scores = generate_wallet_scores()

    if calculated_scores:
        print("\n--- Wallet Credit Scores ---")
        # Print a few examples or all if the dataset is small
        count = 0
        for wallet, score in calculated_scores.items():
            print(f"Wallet: {wallet}, Score: {score}")
            count += 1
            if count >= 10 and len(calculated_scores) > 10: # Just show top 10 if many wallets
                print(f"... and {len(calculated_scores) - 10} more wallets.")
                break

        # Save the results to a JSON file for easy sharing or further analysis
        output_filename = "wallet_credit_scores.json"
        try:
            with open(output_filename, "w") as outfile:
                json.dump(calculated_scores, outfile, indent=4)
            print(f"\nAll scores have been successfully saved to '{output_filename}'")
        except Exception as e:
            print(f"Error saving scores to file: {e}")
    else:
        print("No scores were generated. Please check the input file and data for issues.")


