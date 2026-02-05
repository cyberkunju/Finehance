"""Training data preparation for transaction categorization model."""

import pandas as pd
from typing import List, Tuple


def generate_synthetic_training_data() -> pd.DataFrame:
    """
    Generate synthetic transaction data for training the global categorization model.

    This creates a dataset with transaction descriptions and their corresponding categories.
    In a production environment, this would be replaced with real public datasets.

    Returns:
        DataFrame with 'description' and 'category' columns
    """
    # Define categories and example descriptions
    training_samples = [
        # Groceries
        ("Whole Foods Market", "Groceries"),
        ("Trader Joe's", "Groceries"),
        ("Safeway", "Groceries"),
        ("Kroger", "Groceries"),
        ("Walmart Grocery", "Groceries"),
        ("Target Grocery", "Groceries"),
        ("Costco Wholesale", "Groceries"),
        ("Aldi", "Groceries"),
        ("Publix", "Groceries"),
        ("Fresh Market", "Groceries"),
        ("Sprouts Farmers Market", "Groceries"),
        ("Food Lion", "Groceries"),
        ("Harris Teeter", "Groceries"),
        ("Stop & Shop", "Groceries"),
        ("Giant Food", "Groceries"),
        # Dining
        ("McDonald's", "Dining"),
        ("Starbucks", "Dining"),
        ("Chipotle Mexican Grill", "Dining"),
        ("Subway", "Dining"),
        ("Panera Bread", "Dining"),
        ("Olive Garden", "Dining"),
        ("Red Lobster", "Dining"),
        ("Applebee's", "Dining"),
        ("Chili's", "Dining"),
        ("Buffalo Wild Wings", "Dining"),
        ("Pizza Hut", "Dining"),
        ("Domino's Pizza", "Dining"),
        ("Taco Bell", "Dining"),
        ("Wendy's", "Dining"),
        ("Burger King", "Dining"),
        ("KFC", "Dining"),
        ("Dunkin Donuts", "Dining"),
        ("Five Guys", "Dining"),
        ("In-N-Out Burger", "Dining"),
        ("Shake Shack", "Dining"),
        # Transportation
        ("Shell Gas Station", "Transportation"),
        ("Chevron", "Transportation"),
        ("BP Gas", "Transportation"),
        ("Exxon Mobil", "Transportation"),
        ("Uber", "Transportation"),
        ("Lyft", "Transportation"),
        ("Metro Transit", "Transportation"),
        ("Amtrak", "Transportation"),
        ("Southwest Airlines", "Transportation"),
        ("Delta Airlines", "Transportation"),
        ("United Airlines", "Transportation"),
        ("American Airlines", "Transportation"),
        ("Car Wash", "Transportation"),
        ("Auto Repair Shop", "Transportation"),
        ("Jiffy Lube", "Transportation"),
        ("Parking Meter", "Transportation"),
        ("Toll Road", "Transportation"),
        # Utilities
        ("Electric Company", "Utilities"),
        ("Gas Company", "Utilities"),
        ("Water Department", "Utilities"),
        ("Internet Service", "Utilities"),
        ("Cable TV", "Utilities"),
        ("Phone Bill", "Utilities"),
        ("Verizon", "Utilities"),
        ("AT&T", "Utilities"),
        ("Comcast", "Utilities"),
        ("Spectrum", "Utilities"),
        ("T-Mobile", "Utilities"),
        ("Sprint", "Utilities"),
        # Entertainment
        ("Netflix", "Entertainment"),
        ("Spotify", "Entertainment"),
        ("Hulu", "Entertainment"),
        ("Disney Plus", "Entertainment"),
        ("HBO Max", "Entertainment"),
        ("Amazon Prime Video", "Entertainment"),
        ("Apple Music", "Entertainment"),
        ("YouTube Premium", "Entertainment"),
        ("Movie Theater", "Entertainment"),
        ("AMC Theaters", "Entertainment"),
        ("Regal Cinemas", "Entertainment"),
        ("Concert Tickets", "Entertainment"),
        ("Ticketmaster", "Entertainment"),
        ("Steam Games", "Entertainment"),
        ("PlayStation Store", "Entertainment"),
        ("Xbox Store", "Entertainment"),
        ("Nintendo eShop", "Entertainment"),
        # Healthcare
        ("CVS Pharmacy", "Healthcare"),
        ("Walgreens", "Healthcare"),
        ("Rite Aid", "Healthcare"),
        ("Doctor's Office", "Healthcare"),
        ("Dentist", "Healthcare"),
        ("Hospital", "Healthcare"),
        ("Urgent Care", "Healthcare"),
        ("Lab Tests", "Healthcare"),
        ("Medical Clinic", "Healthcare"),
        ("Eye Doctor", "Healthcare"),
        ("Physical Therapy", "Healthcare"),
        # Shopping
        ("Amazon", "Shopping"),
        ("Target", "Shopping"),
        ("Walmart", "Shopping"),
        ("Best Buy", "Shopping"),
        ("Home Depot", "Shopping"),
        ("Lowe's", "Shopping"),
        ("Macy's", "Shopping"),
        ("Nordstrom", "Shopping"),
        ("Gap", "Shopping"),
        ("Old Navy", "Shopping"),
        ("H&M", "Shopping"),
        ("Zara", "Shopping"),
        ("Nike", "Shopping"),
        ("Adidas", "Shopping"),
        ("Apple Store", "Shopping"),
        ("IKEA", "Shopping"),
        ("Bed Bath & Beyond", "Shopping"),
        ("TJ Maxx", "Shopping"),
        ("Ross", "Shopping"),
        ("Marshalls", "Shopping"),
        # Travel
        ("Hotel Booking", "Travel"),
        ("Marriott", "Travel"),
        ("Hilton", "Travel"),
        ("Airbnb", "Travel"),
        ("Expedia", "Travel"),
        ("Booking.com", "Travel"),
        ("Hertz Rent A Car", "Travel"),
        ("Enterprise Rent-A-Car", "Travel"),
        ("Budget Car Rental", "Travel"),
        # Education
        ("Tuition Payment", "Education"),
        ("Textbook Store", "Education"),
        ("Online Course", "Education"),
        ("Udemy", "Education"),
        ("Coursera", "Education"),
        ("LinkedIn Learning", "Education"),
        ("School Supplies", "Education"),
        # Housing
        ("Rent Payment", "Housing"),
        ("Mortgage Payment", "Housing"),
        ("Property Tax", "Housing"),
        ("HOA Fee", "Housing"),
        ("Home Insurance", "Housing"),
        ("Apartment Complex", "Housing"),
        # Insurance
        ("Car Insurance", "Insurance"),
        ("Health Insurance", "Insurance"),
        ("Life Insurance", "Insurance"),
        ("Dental Insurance", "Insurance"),
        ("Vision Insurance", "Insurance"),
        ("Renters Insurance", "Insurance"),
        # Salary (Income)
        ("Payroll Deposit", "Salary"),
        ("Direct Deposit", "Salary"),
        ("Salary Payment", "Salary"),
        ("Paycheck", "Salary"),
        # Freelance (Income)
        ("Freelance Payment", "Freelance"),
        ("Consulting Fee", "Freelance"),
        ("Contract Work", "Freelance"),
        ("Upwork Payment", "Freelance"),
        ("Fiverr Payment", "Freelance"),
        # Investment (Income)
        ("Dividend Payment", "Investment"),
        ("Stock Sale", "Investment"),
        ("Interest Income", "Investment"),
        ("Capital Gains", "Investment"),
        # Other Income
        ("Tax Refund", "Other Income"),
        ("Gift Money", "Other Income"),
        ("Bonus", "Other Income"),
        ("Reimbursement", "Other Income"),
        # Other Expenses
        ("ATM Withdrawal", "Other Expenses"),
        ("Bank Fee", "Other Expenses"),
        ("Late Fee", "Other Expenses"),
        ("Subscription", "Other Expenses"),
        ("Donation", "Other Expenses"),
        ("Charity", "Other Expenses"),
        ("Pet Store", "Other Expenses"),
        ("Veterinarian", "Other Expenses"),
        ("Gym Membership", "Other Expenses"),
        ("Fitness Club", "Other Expenses"),
    ]

    # Create DataFrame
    df = pd.DataFrame(training_samples, columns=["description", "category"])

    # Add variations with different cases and extra words
    variations = []
    for desc, cat in training_samples:
        # Lowercase variation
        variations.append((desc.lower(), cat))
        # Uppercase variation
        variations.append((desc.upper(), cat))
        # With transaction ID
        variations.append((f"{desc} #12345", cat))
        # With date
        variations.append((f"{desc} 01/15/2024", cat))
        # With amount
        variations.append((f"{desc} $50.00", cat))

    # Add variations to DataFrame
    variations_df = pd.DataFrame(variations, columns=["description", "category"])
    df = pd.concat([df, variations_df], ignore_index=True)

    # Shuffle the data
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)

    return df


def preprocess_text(text: str) -> str:
    """
    Preprocess transaction description text.

    Steps:
    1. Convert to lowercase
    2. Remove special characters (keep alphanumeric and spaces)
    3. Remove extra whitespace

    Args:
        text: Raw transaction description

    Returns:
        Preprocessed text
    """
    import re

    # Convert to lowercase
    text = text.lower()

    # Remove special characters (keep letters, numbers, and spaces)
    text = re.sub(r"[^a-z0-9\s]", " ", text)

    # Remove extra whitespace
    text = " ".join(text.split())

    return text


def prepare_training_data() -> Tuple[List[str], List[str]]:
    """
    Prepare training data for the categorization model.

    Returns:
        Tuple of (descriptions, categories)
    """
    # Generate synthetic data
    df = generate_synthetic_training_data()

    # Preprocess descriptions
    df["description"] = df["description"].apply(preprocess_text)

    # Remove duplicates
    df = df.drop_duplicates(subset=["description"])

    return df["description"].tolist(), df["category"].tolist()


if __name__ == "__main__":
    # Test data generation
    descriptions, categories = prepare_training_data()
    print(f"Generated {len(descriptions)} training samples")
    print(f"Categories: {set(categories)}")
    print("\nSample data:")
    for i in range(5):
        print(f"  {descriptions[i]} -> {categories[i]}")
