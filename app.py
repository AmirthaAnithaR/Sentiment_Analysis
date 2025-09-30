# app.py

import sys
import os
import pandas as pd
import numpy as np
import string
from textblob import TextBlob
from nltk.corpus import stopwords
import nltk
from wordcloud import WordCloud
import io
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend to avoid warning
import matplotlib.pyplot as plt
import base64
from datetime import datetime
import json
import time
import random
from collections import Counter
import re
from flask import Flask, jsonify, render_template_string, send_file, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
from functools import wraps
import tempfile
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors

# Check for potential naming conflicts
conflicting_files = ['enum.py', 'typing.py', 're.py', 'collections.py', 'datetime.py', 'json.py', 'os.py', 'sys.py']
for file in conflicting_files:
    if os.path.exists(file):
        print(f"ERROR: Found '{file}' in current directory. This conflicts with Python's standard library.")
        print(f"Please rename or remove '{file}' to avoid import issues.")
        sys.exit(1)

try:
    from flask import Flask, jsonify, render_template_string, send_file, request, redirect, url_for, flash, session
    from flask_sqlalchemy import SQLAlchemy
    from werkzeug.security import generate_password_hash, check_password_hash
    from functools import wraps
    import pandas as pd
    import string
    from textblob import TextBlob
    from nltk.corpus import stopwords
    import nltk
    from wordcloud import WordCloud
    import io
    import matplotlib
    matplotlib.use('Agg')  # Use non-interactive backend to avoid warning
    import matplotlib.pyplot as plt
    import base64
    from datetime import datetime
    import json
    import time
    import random
    from collections import Counter
    import re
except ImportError as e:
    print(f"Import error: {e}")
    print("Please ensure all required packages are installed.")
    sys.exit(1)
except Exception as e:
    print(f"Unexpected error during imports: {e}")
    sys.exit(1)

# Download stopwords if not already
try:
    nltk.data.find('corpora/stopwords')
except nltk.downloader.DownloadError:
    nltk.download('stopwords')

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Change this to a secure secret key
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///comments.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)

# User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# Comment model for user-submitted comments
class UserComment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    sentiment = db.Column(db.String(20))
    detailed_sentiment = db.Column(db.String(20))  # New field for detailed sentiment
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user = db.relationship('User', backref=db.backref('comments', lazy=True))

# Create tables
with app.app_context():
    try:
        db.create_all()
        
        # Create default admin user if not exists
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', is_admin=True)
            admin.set_password('admin123')  # Change this password in production
            db.session.add(admin)
            db.session.commit()
    except Exception as e:
        print(f"Database initialization error: {e}")
        sys.exit(1)

# Load dataset function - now loads from TaxTruth_Exploitation.csv
def load_dataset():
    """Load dataset from TaxTruth_Exploitation.csv"""
    try:
        print("Loading TaxTruth_Exploitation dataset from CSV...")
        df = pd.read_csv("TaxTruth_Exploitation.csv")
        print(f"Loaded {len(df)} records from TaxTruth_Exploitation dataset")
        
        # Check if required columns exist
        if 'PersonalComment' not in df.columns:
            print("Warning: 'PersonalComment' column not found in CSV")
            # Create a default comment column
            df['PersonalComment'] = "No comment provided"
        
        # Create a username column based on ID
        if 'Username' not in df.columns:
            print("Adding 'Username' column...")
            df['Username'] = [f"User{i+1}" for i in range(len(df))]
        
        # Create a date column if it doesn't exist
        if 'Date' not in df.columns:
            print("Adding 'Date' column...")
            df['Date'] = datetime.now().strftime("%Y-%m-%d")
        
        # Rename PersonalComment to Comment Text for consistency
        df = df.rename(columns={'PersonalComment': 'Comment Text'})
        
        return df
    except FileNotFoundError:
        print("TaxTruth_Exploitation.csv file not found. Creating sample dataset...")
        # Create sample data if file doesn't exist
        data = {
            "ID": [1, 2, 3, 4, 5],
            "PersonType": ["Poor", "MiddleClass", "Rich", "Billionaire", "Poor"],
            "Profession": ["Delivery Partner", "Nurse", "IT Engineer", "CEO", "Street Vendor"],
            "MonthlyIncome": [8701, 45227, 65454, 96818535, 14429],
            "TaxPaid": [871, 6633, 24370, 0, 871],
            "GSTItemsUsed": ["Petrol, Electricity", "Basic Groceries, Medical Supplies", "Cooking Gas, Basic Groceries", "Clothing, Fuel", "Electricity, Internet"],
            "GovernmentBenefit": ["Yes", "Yes", "No", "No", "Yes"],
            "BillionaireNearby": ["No", "No", "No", "Yes", "No"],
            "BillionaireTaxKnown": ["₹1000", "₹Unknown", "₹Unknown", "₹Unknown", "₹5000"],
            "FeelingExploited": ["Yes", "Yes", "No", "No", "Yes"],
            "PersonalComment": [
                "Why is everything taxed but not billionaires?",
                "Why is everything taxed but not billionaires?",
                "System is one-sided.",
                "System is one-sided.",
                "GST is killing my income."
            ],
            "Location": ["Jaipur, RJ", "Amritsar, PB", "Pune, MH", "Nagpur, MH", "Hyderabad, TS"]
        }
        df = pd.DataFrame(data)
        # Save the sample data to CSV file
        df.to_csv("TaxTruth_Exploitation.csv", index=False)
        print("Created sample TaxTruth dataset with 5 records")
        
        # Rename PersonalComment to Comment Text for consistency
        df = df.rename(columns={'PersonalComment': 'Comment Text'})
        
        # Create a username column based on ID
        df['Username'] = [f"User{i+1}" for i in range(len(df))]
        
        # Create a date column if it doesn't exist
        df['Date'] = datetime.now().strftime("%Y-%m-%d")
        
        return df
    except Exception as e:
        print(f"Error loading TaxTruth_Exploitation dataset: {e}")
        # Create empty dataframe as fallback
        return pd.DataFrame(columns=["Comment Text", "Date", "Username"])

# Text Preprocessing
stop_words = set(stopwords.words("english"))

def preprocess(text):
    if not isinstance(text, str):
        return ""
    text = text.lower()
    text = text.translate(str.maketrans("", "", string.punctuation))
    words = [w for w in text.split() if w not in stop_words]
    return " ".join(words)

# Sentiment analysis function
def get_sentiment(text):
    analysis = TextBlob(text)
    polarity = analysis.sentiment.polarity
    
    # Basic sentiment classification
    if polarity > 0:
        return "positive"
    elif polarity < 0:
        return "negative"
    else:
        return "neutral"

# Detailed sentiment analysis function
def get_detailed_sentiment(text):
    analysis = TextBlob(text)
    polarity = analysis.sentiment.polarity
    subjectivity = analysis.sentiment.subjectivity
    
    # More nuanced sentiment classification with adjusted thresholds
    if polarity > 0.3:
        return "strong-positive"  # Strongly positive
    elif polarity > 0:
        return "weak-positive"  # Weakly positive
    elif polarity > -0.3:
        return "weak-negative"  # Weakly negative
    else:
        return "strong-negative"  # Strongly negative

# Improved AI Summarizer function - now generates abstract summary and separate sentiment summaries
def generate_ai_summary(df):
    # Group by sentiment and ensure we have valid strings
    positive_comments = df[df['sentiment'] == 'positive']['Comment Text'].dropna().astype(str).tolist()
    negative_comments = df[df['sentiment'] == 'negative']['Comment Text'].dropna().astype(str).tolist()
    neutral_comments = df[df['sentiment'] == 'neutral']['Comment Text'].dropna().astype(str).tolist()
    
    # Group by detailed sentiment
    strong_positive_comments = df[df['detailed_sentiment'] == 'strong-positive']['Comment Text'].dropna().astype(str).tolist()
    weak_positive_comments = df[df['detailed_sentiment'] == 'weak-positive']['Comment Text'].dropna().astype(str).tolist()
    weak_negative_comments = df[df['detailed_sentiment'] == 'weak-negative']['Comment Text'].dropna().astype(str).tolist()
    strong_negative_comments = df[df['detailed_sentiment'] == 'strong-negative']['Comment Text'].dropna().astype(str).tolist()
    
    # Calculate counts and percentages
    total_comments = len(df)
    pos_count = len(positive_comments)
    neg_count = len(negative_comments)
    neu_count = len(neutral_comments)
    
    pos_pct = round((pos_count / total_comments) * 100, 1) if total_comments > 0 else 0
    neg_pct = round((neg_count / total_comments) * 100, 1) if total_comments > 0 else 0
    neu_pct = round((neu_count / total_comments) * 100, 1) if total_comments > 0 else 0
    
    # Detailed sentiment counts
    strong_positive_count = len(strong_positive_comments)
    weak_positive_count = len(weak_positive_comments)
    weak_negative_count = len(weak_negative_comments)
    strong_negative_count = len(strong_negative_comments)
    
    strong_positive_pct = round((strong_positive_count / total_comments) * 100, 1) if total_comments > 0 else 0
    weak_positive_pct = round((weak_positive_count / total_comments) * 100, 1) if total_comments > 0 else 0
    weak_negative_pct = round((weak_negative_count / total_comments) * 100, 1) if total_comments > 0 else 0
    strong_negative_pct = round((strong_negative_count / total_comments) * 100, 1) if total_comments > 0 else 0
    
    # Extract keywords for the entire dataset
    def extract_keywords(comments, n=10):
        if not comments:
            return []
        all_text = ' '.join(comments)
        words = preprocess(all_text).split()
        word_freq = Counter(words)
        return [word for word, count in word_freq.most_common(n)]
    
    all_keywords = extract_keywords(df['Comment Text'].tolist(), 10)
    
    # Analyze sentiment by PersonType
    sentiment_by_type = {}
    if 'PersonType' in df.columns:
        for ptype in df['PersonType'].unique():
            type_df = df[df['PersonType'] == ptype]
            type_total = len(type_df)
            if type_total > 0:
                type_pos = len(type_df[type_df['sentiment'] == 'positive'])
                type_neg = len(type_df[type_df['sentiment'] == 'negative'])
                type_neu = len(type_df[type_df['sentiment'] == 'neutral'])
                sentiment_by_type[ptype] = {
                    'positive': round((type_pos / type_total) * 100, 1),
                    'negative': round((type_neg / type_total) * 100, 1),
                    'neutral': round((type_neu / type_total) * 100, 1),
                    'count': type_total
                }
    
    # Analyze FeelingExploited distribution
    feeling_exploited_dist = {}
    if 'FeelingExploited' in df.columns:
        feeling_counts = df['FeelingExploited'].value_counts()
        for feeling in feeling_counts.index:
            feeling_exploited_dist[feeling] = {
                'count': feeling_counts[feeling],
                'percentage': round((feeling_counts[feeling] / total_comments) * 100, 1)
            }
    
    # Generate abstract summary
    abstract_parts = []
    
    # Overall sentiment
    if pos_pct > neg_pct and pos_pct > neu_pct:
        overall_sentiment = "predominantly positive"
    elif neg_pct > pos_pct and neg_pct > neu_pct:
        overall_sentiment = "predominantly negative"
    else:
        overall_sentiment = "mixed"
    
    abstract_parts.append(f"This analysis of {total_comments} comments reveals a {overall_sentiment} sentiment toward the tax system, with {pos_pct}% positive, {neg_pct}% negative, and {neu_pct}% neutral responses.")
    
    # Key themes
    if all_keywords:
        top_themes = ', '.join(all_keywords[:5])
        abstract_parts.append(f"Key themes emerging from the comments include {top_themes}.")
    
    # Sentiment by PersonType
    if sentiment_by_type:
        type_sentiments = []
        for ptype, data in sentiment_by_type.items():
            if data['negative'] > data['positive'] and data['negative'] > data['neutral']:
                type_sentiments.append(f"{ptype} respondents express predominantly negative sentiment ({data['negative']}%)")
            elif data['positive'] > data['negative'] and data['positive'] > data['neutral']:
                type_sentiments.append(f"{ptype} respondents express predominantly positive sentiment ({data['positive']}%)")
        
        if type_sentiments:
            abstract_parts.append(f"Notable patterns by economic status include: {', '.join(type_sentiments)}.")
    
    # FeelingExploited
    if feeling_exploited_dist:
        if 'Yes' in feeling_exploited_dist:
            exploited_pct = feeling_exploited_dist['Yes']['percentage']
            abstract_parts.append(f"Significantly, {exploited_pct}% of respondents report feeling exploited by the current tax system.")
    
    # Conclusion
    if neg_pct > 50:
        abstract_parts.append("The overall sentiment suggests widespread dissatisfaction with the tax system, particularly regarding fairness and equity.")
    elif pos_pct > 50:
        abstract_parts.append("The overall sentiment indicates general satisfaction with the tax system, though some concerns remain.")
    else:
        abstract_parts.append("The sentiment is divided, reflecting diverse perspectives on the tax system's effectiveness and fairness.")
    
    abstract_summary = ' '.join(abstract_parts)
    
    # Generate separate summaries for each sentiment
    # Positive summary
    positive_summary_parts = []
    if positive_comments:
        positive_keywords = extract_keywords(positive_comments, 5)
        positive_summary_parts.append(f"The positive sentiment analysis ({pos_pct}% of comments) reveals aspects of the tax system that respondents appreciate. Key themes include {', '.join(positive_keywords[:3])}.")
        
        # Analyze positive sentiment by PersonType
        positive_by_type = {}
        if 'PersonType' in df.columns:
            for ptype in df['PersonType'].unique():
                type_df = df[df['PersonType'] == ptype]
                type_positive = type_df[type_df['sentiment'] == 'positive']
                if len(type_positive) > 0:
                    positive_by_type[ptype] = len(type_positive)
            
            if positive_by_type:
                most_positive = max(positive_by_type, key=positive_by_type.get)
                positive_summary_parts.append(f"The {most_positive} group shows the highest number of positive comments.")
        
        positive_summary_parts.append("These positive comments suggest areas where the tax system is functioning well and meeting public expectations.")
    else:
        positive_summary_parts.append("No positive comments were found in the dataset.")
    
    positive_summary = ' '.join(positive_summary_parts)
    
    # Negative summary
    negative_summary_parts = []
    if negative_comments:
        negative_keywords = extract_keywords(negative_comments, 5)
        negative_summary_parts.append(f"The negative sentiment analysis ({neg_pct}% of comments) highlights significant concerns about the tax system. Key issues include {', '.join(negative_keywords[:3])}.")
        
        # Analyze negative sentiment by PersonType
        negative_by_type = {}
        if 'PersonType' in df.columns:
            for ptype in df['PersonType'].unique():
                type_df = df[df['PersonType'] == ptype]
                type_negative = type_df[type_df['sentiment'] == 'negative']
                if len(type_negative) > 0:
                    negative_by_type[ptype] = len(type_negative)
            
            if negative_by_type:
                most_negative = max(negative_by_type, key=negative_by_type.get)
                negative_summary_parts.append(f"The {most_negative} group expresses the most negative sentiment.")
        
        negative_summary_parts.append("These negative comments indicate areas where the tax system may need reform or improvement.")
    else:
        negative_summary_parts.append("No negative comments were found in the dataset.")
    
    negative_summary = ' '.join(negative_summary_parts)
    
    # Neutral summary
    neutral_summary_parts = []
    if neutral_comments:
        neutral_keywords = extract_keywords(neutral_comments, 5)
        neutral_summary_parts.append(f"The neutral sentiment analysis ({neu_pct}% of comments) provides factual observations about the tax system. Key topics include {', '.join(neutral_keywords[:3])}.")
        
        # Analyze neutral sentiment by PersonType
        neutral_by_type = {}
        if 'PersonType' in df.columns:
            for ptype in df['PersonType'].unique():
                type_df = df[df['PersonType'] == ptype]
                type_neutral = type_df[type_df['sentiment'] == 'neutral']
                if len(type_neutral) > 0:
                    neutral_by_type[ptype] = len(type_neutral)
            
            if neutral_by_type:
                most_neutral = max(neutral_by_type, key=neutral_by_type.get)
                neutral_summary_parts.append(f"The {most_neutral} group provides the most neutral comments.")
        
        neutral_summary_parts.append("These neutral comments offer balanced perspectives and objective assessments of the tax system.")
    else:
        neutral_summary_parts.append("No neutral comments were found in the dataset.")
    
    neutral_summary = ' '.join(neutral_summary_parts)
    
    return {
        "abstract": abstract_summary,
        "positive_summary": positive_summary,
        "negative_summary": negative_summary,
        "neutral_summary": neutral_summary,
        "statistics": {
            "total": total_comments,
            "positive": {
                "count": pos_count,
                "percentage": pos_pct
            },
            "negative": {
                "count": neg_count,
                "percentage": neg_pct
            },
            "neutral": {
                "count": neu_count,
                "percentage": neu_pct
            },
            "detailed": {
                "strong-positive": {
                    "count": strong_positive_count,
                    "percentage": strong_positive_pct
                },
                "weak-positive": {
                    "count": weak_positive_count,
                    "percentage": weak_positive_pct
                },
                "weak-negative": {
                    "count": weak_negative_count,
                    "percentage": weak_negative_pct
                },
                "strong-negative": {
                    "count": strong_negative_count,
                    "percentage": strong_negative_pct
                }
            },
            "sentiment_by_type": sentiment_by_type,
            "feeling_exploited": feeling_exploited_dist
        }
    }

def process_data(df):
    # Ensure all comments are strings and handle NaN values
    df['Comment Text'] = df['Comment Text'].fillna('').astype(str)
    
    print(f"Processing {len(df)} comments...")
    
    print("Preprocessing text...")
    df["cleaned_text"] = df["Comment Text"].apply(preprocess)
    
    # Sentiment Analysis
    print("Performing sentiment analysis...")
    try:
        df["sentiment"] = df["cleaned_text"].apply(get_sentiment)
        df["detailed_sentiment"] = df["cleaned_text"].apply(get_detailed_sentiment)
        print("Sentiment analysis completed.")
        
        # Print detailed sentiment distribution for debugging
        print("\nDetailed sentiment distribution:")
        print(df['detailed_sentiment'].value_counts())
        
    except Exception as e:
        print(f"Error during sentiment analysis: {e}")
        # Fallback: assign neutral sentiment to all
        df["sentiment"] = "neutral"
        df["detailed_sentiment"] = "weak-negative"
    
    # Print sample of processed data for debugging
    print("\nSample of processed data:")
    print(df[['Comment Text', 'sentiment', 'detailed_sentiment']].head(5))
    
    # Calculate sentiment counts and percentages
    sentiment_counts = df['sentiment'].value_counts().to_dict()
    total_comments = len(df)
    sentiment_percentages = {
        "positive": round((sentiment_counts.get("positive", 0) / total_comments) * 100, 2) if total_comments else 0,
        "negative": round((sentiment_counts.get("negative", 0) / total_comments) * 100, 2) if total_comments else 0,
        "neutral": round((sentiment_counts.get("neutral", 0) / total_comments) * 100, 2) if total_comments else 0,
    }
    
    # Calculate detailed sentiment counts and percentages
    detailed_sentiment_counts = df['detailed_sentiment'].value_counts().to_dict()
    detailed_sentiment_percentages = {
        "strong-positive": round((detailed_sentiment_counts.get("strong-positive", 0) / total_comments) * 100, 2) if total_comments else 0,
        "weak-positive": round((detailed_sentiment_counts.get("weak-positive", 0) / total_comments) * 100, 2) if total_comments else 0,
        "weak-negative": round((detailed_sentiment_counts.get("weak-negative", 0) / total_comments) * 100, 2) if total_comments else 0,
        "strong-negative": round((detailed_sentiment_counts.get("strong-negative", 0) / total_comments) * 100, 2) if total_comments else 0,
    }
    
    print(f"\nSentiment distribution: {sentiment_percentages}")
    print(f"Detailed sentiment distribution: {detailed_sentiment_percentages}")
    print(f"Total comments processed: {total_comments}")
    
    # Get sentiment by month
    if 'Date' in df.columns:
        # Try to parse dates with explicit format
        try:
            df['Date'] = pd.to_datetime(df['Date'], format='%Y-%m-%d')
        except:
            # If that fails, try to infer the format
            df['Date'] = pd.to_datetime(df['Date'], format='mixed')
        
        df['Month'] = df['Date'].dt.strftime('%b')
        monthly_sentiment = df.groupby(['Month', 'sentiment']).size().unstack(fill_value=0).to_dict()
    else:
        monthly_sentiment = {
            'positive': {'Jan': 65, 'Feb': 59, 'Mar': 70, 'Apr': 71, 'May': 66, 'Jun': 65, 'Jul': 72, 'Aug': 68, 'Sep': 64},
            'negative': {'Jan': 15, 'Feb': 19, 'Mar': 12, 'Apr': 13, 'May': 16, 'Jun': 15, 'Jul': 14, 'Aug': 19, 'Sep': 19},
            'neutral': {'Jan': 20, 'Feb': 22, 'Mar': 18, 'Apr': 16, 'May': 18, 'Jun': 20, 'Jul': 14, 'Aug': 13, 'Sep': 17}
        }
    
    # Get top keywords with frequencies
    all_words = ' '.join(df['cleaned_text']).split()
    word_freq = Counter(all_words)
    top_keywords = [word for word, count in word_freq.most_common(20)]
    
    # Get recent comments with proper sentiment distribution
    print("Selecting recent comments with sentiment distribution...")
    
    # Sort by date if available, otherwise by index
    if 'Date' in df.columns:
        # Try to parse dates with explicit format
        try:
            df['Date'] = pd.to_datetime(df['Date'], format='%Y-%m-%d')
        except:
            # If that fails, try to infer the format
            df['Date'] = pd.to_datetime(df['Date'], format='mixed')
        
        # Sort by date descending to get most recent first
        df_sorted = df.sort_values(by='Date', ascending=False)
    else:
        # If no date column, reverse the order to get most recent first (assuming original is chronological)
        df_sorted = df.iloc[::-1].reset_index(drop=True)

    # Check if 'Username' column exists before trying to access it
    if 'Username' not in df_sorted.columns:
        df_sorted['Username'] = [f"User{i+1}" for i in range(len(df_sorted))]

    # Take the top 5 most recent comments
    top_5 = df_sorted.head(5).copy()

    # Get the set of sentiments in the top_5
    sentiments_in_top5 = set(top_5['sentiment'].unique())
    all_sentiments = {'positive', 'negative', 'neutral'}
    missing_sentiments = all_sentiments - sentiments_in_top5

    # For each missing sentiment, get the most recent comment of that sentiment
    additional_comments = []
    for sentiment in missing_sentiments:
        # Get comments of this sentiment, sorted by date (descending)
        sentiment_comments = df_sorted[df_sorted['sentiment'] == sentiment]
        if not sentiment_comments.empty:
            # Take the first one (most recent)
            candidate = sentiment_comments.iloc[0]
            # Check if candidate is already in top_5 (by index)
            if candidate.name not in top_5.index:
                additional_comments.append(candidate)

    # Combine top_5 and additional_comments
    combined = pd.concat([top_5, pd.DataFrame(additional_comments)])

    # Sort combined by date (descending) if available, otherwise by the original order in combined
    if 'Date' in combined.columns:
        combined = combined.sort_values(by='Date', ascending=False)
    # else: we keep the order (top_5 first, then additional_comments)

    # Take the top 5
    recent_comments = combined.head(5)[["Comment Text", "sentiment", "detailed_sentiment", "Username"]].to_dict('records')
    
    # Check if 'Username' column exists before trying to access it
    if 'Username' in df.columns:
        comments_data = df[["Comment Text", "sentiment", "detailed_sentiment", "Username"]].to_dict(orient="records")
    else:
        # If 'Username' column doesn't exist, create it with default values
        df['Username'] = [f"User{i+1}" for i in range(len(df))]
        comments_data = df[["Comment Text", "sentiment", "detailed_sentiment", "Username"]].to_dict(orient="records")
    
    # Combine all cleaned text into one string
    all_text = " ".join(df["cleaned_text"].tolist())
    
    # Generate separate text for each sentiment for word clouds
    positive_text = " ".join(df[df['sentiment'] == 'positive']['cleaned_text'].tolist())
    negative_text = " ".join(df[df['sentiment'] == 'negative']['cleaned_text'].tolist())
    neutral_text = " ".join(df[df['sentiment'] == 'neutral']['cleaned_text'].tolist())
    
    # Generate AI summaries
    print("Generating AI summaries...")
    ai_summaries = generate_ai_summary(df)
    print("AI summaries generated.")
    
    # Calculate section sentiment data
    print("Calculating section sentiment data...")
    section_sentiment = calculate_section_sentiment(df)
    
    # Generate word clouds and store as base64 strings
    print("Generating word clouds...")
    all_wordcloud_base64 = generate_wordcloud_base64(all_text)
    positive_wordcloud_base64 = generate_wordcloud_base64(positive_text, color="#2ecc71")
    negative_wordcloud_base64 = generate_wordcloud_base64(negative_text, color="#e74c3c")
    neutral_wordcloud_base64 = generate_wordcloud_base64(neutral_text, color="#3498db")
    print("Word clouds generated.")
    
    # Process comments for highlighting important keywords
    print("Processing comments for keyword highlighting...")
    highlighted_comments = []
    for _, row in df.iterrows():
        comment_text = row['Comment Text']
        cleaned_text = row['cleaned_text']
        
        # Get important words from the cleaned text
        words = cleaned_text.split()
        important_words = [word for word in words if word in top_keywords[:10]]
        
        # Create a mapping of original words to their highlighted versions
        highlighted_mapping = {}
        for word in important_words:
            # Find the original word in the comment (case-insensitive)
            pattern = re.compile(r'\b' + re.escape(word) + r'\b', re.IGNORECASE)
            highlighted_mapping[word] = pattern
        
        # Apply highlighting to the comment text
        highlighted_comment = comment_text
        for word, pattern in highlighted_mapping.items():
            highlighted_comment = pattern.sub(f'<u>{word}</u>', highlighted_comment)
        
        highlighted_comments.append({
            'Comment Text': highlighted_comment,
            'sentiment': row['sentiment'],
            'detailed_sentiment': row['detailed_sentiment'],
            'Username': row['Username']
        })
    
    print("Comments processed for keyword highlighting.")
    
    return {
        "df": df,
        "sentiment_percentages": sentiment_percentages,
        "detailed_sentiment_percentages": detailed_sentiment_percentages,
        "total_comments": total_comments,
        "monthly_sentiment": monthly_sentiment,
        "top_keywords": top_keywords,
        "recent_comments": recent_comments,
        "comments_data": comments_data,
        "all_text": all_text,
        "positive_text": positive_text,
        "negative_text": negative_text,
        "neutral_text": neutral_text,
        "ai_summaries": ai_summaries,
        "section_sentiment": section_sentiment,
        "all_wordcloud_base64": all_wordcloud_base64,
        "positive_wordcloud_base64": positive_wordcloud_base64,
        "negative_wordcloud_base64": negative_wordcloud_base64,
        "neutral_wordcloud_base64": neutral_wordcloud_base64,
        "highlighted_comments": highlighted_comments
    }

def calculate_section_sentiment(df):
    # Define sections and keywords associated with each section
    sections = {
        "A1: Centralization": ["centralization", "central", "authority", "control", "power", "government", "initiative", "policy", "rule", "rules"],
        "A2: Compliance": ["compliance", "regulation", "rules", "adherence", "requirements", "follow", "obey", "law", "regulations"],
        "A3: Transparency": ["transparency", "open", "clear", "disclosure", "visibility", "transparent", "clarity", "understand"],
        "B1: Implementation": ["implementation", "execution", "enforcement", "apply", "deploy", "carry", "put", "effect", "implementing"],
        "B2: Regulation": ["regulation", "regulate", "rules", "standards", "guidelines", "law", "policy", "regulating"],
        "B3: Accountability": ["accountability", "responsible", "answerable", "liability", "oversight", "responsibility", "answer"],
        "C1: Data Rights": ["rights", "privacy", "consent", "ownership", "access", "data", "protection", "right"],
        "C2: Security": ["security", "protection", "safe", "secure", "breach", "safety", "protect"],
        "C3: Enforcement": ["enforcement", "penalty", "punishment", "fine", "sanction", "impose", "enforce", "enforcing"],
        "D1: Oversight": ["oversight", "monitor", "supervise", "watch", "inspect", "supervision", "monitoring"],
        "D2: User Control": ["control", "user", "choice", "option", "preference", "user control", "choices"],
        "D3: Breach Notification": ["breach", "notification", "alert", "inform", "report", "notify", "notifying"]
    }
    
    section_data = {}
    
    # Debug: Print first few comments to see what words we're working with
    print("Sample comments for keyword matching:")
    for i, comment in enumerate(df['cleaned_text'].head(5)):
        print(f"{i+1}: {comment}")
    
    for section, keywords in sections.items():
        print(f"\nProcessing section: {section}")
        print(f"Keywords: {keywords}")
        
        # Find comments that mention keywords for this section
        # Create a regex pattern that matches whole words only
        pattern = r'\b(' + '|'.join(keywords) + r')\b'
        section_comments = df[df['cleaned_text'].str.contains(pattern, case=False, na=False, regex=True)]
        
        print(f"Found {len(section_comments)} matching comments")
        
        if len(section_comments) > 0:
            # Calculate sentiment distribution for this section
            section_sentiment_counts = section_comments['sentiment'].value_counts().to_dict()
            section_total = len(section_comments)
            
            # Calculate detailed sentiment distribution
            section_detailed_sentiment_counts = section_comments['detailed_sentiment'].value_counts().to_dict()
            
            section_data[section] = {
                "positive": round((section_sentiment_counts.get("positive", 0) / section_total) * 100, 1) if section_total else 0,
                "negative": round((section_sentiment_counts.get("negative", 0) / section_total) * 100, 1) if section_total else 0,
                "neutral": round((section_sentiment_counts.get("neutral", 0) / section_total) * 100, 1) if section_total else 0,
                "detailed": {
                    "strong-positive": round((section_detailed_sentiment_counts.get("strong-positive", 0) / section_total) * 100, 1) if section_total else 0,
                    "weak-positive": round((section_detailed_sentiment_counts.get("weak-positive", 0) / section_total) * 100, 1) if section_total else 0,
                    "weak-negative": round((section_detailed_sentiment_counts.get("weak-negative", 0) / section_total) * 100, 1) if section_total else 0,
                    "strong-negative": round((section_detailed_sentiment_counts.get("strong-negative", 0) / section_total) * 100, 1) if section_total else 0,
                },
                "total": section_total,
                "comments": section_comments[["Comment Text", "sentiment", "detailed_sentiment", "Username"]].head(3).to_dict('records')
            }
            
            print(f"Sentiment distribution: {section_data[section]}")
        else:
            # If no comments match, provide default values
            section_data[section] = {
                "positive": 25.0,
                "negative": 25.0,
                "neutral": 25.0,
                "detailed": {
                    "strong-positive": 12.5,
                    "weak-positive": 12.5,
                    "weak-negative": 12.5,
                    "strong-negative": 12.5,
                },
                "total": 0,
                "comments": []
            }
            print("No comments matched, using default values")
    
    return section_data

# Initialize global variables to None
df = None
sentiment_percentages = None
detailed_sentiment_percentages = None
total_comments = None
monthly_sentiment = None
top_keywords = None
recent_comments = None
comments_data = None
all_text = None
positive_text = None
negative_text = None
neutral_text = None
ai_summaries = None
section_sentiment = None
all_wordcloud_base64 = None
positive_wordcloud_base64 = None
negative_wordcloud_base64 = None
neutral_wordcloud_base64 = None
highlighted_comments = None

# Function to load and process data from TaxTruth_Exploitation.csv
def load_and_process_data():
    global df, sentiment_percentages, detailed_sentiment_percentages, total_comments, monthly_sentiment, top_keywords, recent_comments, comments_data, all_text, positive_text, negative_text, neutral_text, ai_summaries, section_sentiment, all_wordcloud_base64, positive_wordcloud_base64, negative_wordcloud_base64, neutral_wordcloud_base64, highlighted_comments

    print("Loading and processing TaxTruth_Exploitation dataset...")
    df = load_dataset()
    
    # If df is empty, create a sample dataframe
    if df.empty:
        print("No data fetched, creating sample data")
        data = [
            {"Comment Text": "This is a great initiative by the government", "Date": "2023-01-15", "Username": "@gov_supporter"},
            {"Comment Text": "I'm not happy with the current regulations", "Date": "2023-02-20", "Username": "@concerned_citizen"},
            {"Comment Text": "The new policy seems reasonable", "Date": "2023-03-10", "Username": "@policy_analyst"},
            {"Comment Text": "This will negatively impact small businesses", "Date": "2023-04-05", "Username": "@business_owner"},
            {"Comment Text": "Looking forward to the implementation", "Date": "2023-05-12", "Username": "@optimist_view"}
        ]
        df = pd.DataFrame(data)
    
    processed_data = process_data(df)
    df = processed_data["df"]
    sentiment_percentages = processed_data["sentiment_percentages"]
    detailed_sentiment_percentages = processed_data["detailed_sentiment_percentages"]
    total_comments = processed_data["total_comments"]
    monthly_sentiment = processed_data["monthly_sentiment"]
    top_keywords = processed_data["top_keywords"]
    recent_comments = processed_data["recent_comments"]
    comments_data = processed_data["comments_data"]
    all_text = processed_data["all_text"]
    positive_text = processed_data["positive_text"]
    negative_text = processed_data["negative_text"]
    neutral_text = processed_data["neutral_text"]
    ai_summaries = processed_data["ai_summaries"]
    section_sentiment = processed_data["section_sentiment"]
    all_wordcloud_base64 = processed_data["all_wordcloud_base64"]
    positive_wordcloud_base64 = processed_data["positive_wordcloud_base64"]
    negative_wordcloud_base64 = processed_data["negative_wordcloud_base64"]
    neutral_wordcloud_base64 = processed_data["neutral_wordcloud_base64"]
    highlighted_comments = processed_data["highlighted_comments"]
    print("Data loading and processing completed.")

# Function to reprocess data from CSV file
def reprocess_data():
    global df, sentiment_percentages, detailed_sentiment_percentages, total_comments, monthly_sentiment, top_keywords, recent_comments, comments_data, all_text, positive_text, negative_text, neutral_text, ai_summaries, section_sentiment, all_wordcloud_base64, positive_wordcloud_base64, negative_wordcloud_base64, neutral_wordcloud_base64, highlighted_comments

    print("Reprocessing data from TaxTruth_Exploitation.csv file...")
    try:
        df = pd.read_csv("TaxTruth_Exploitation.csv")
        print(f"Loaded {len(df)} records from TaxTruth_Exploitation.csv file")
        
        # Rename PersonalComment to Comment Text for consistency
        df = df.rename(columns={'PersonalComment': 'Comment Text'})
        
        # Ensure required columns exist
        if 'Username' not in df.columns:
            print("Adding missing 'Username' column...")
            df['Username'] = [f"User{i+1}" for i in range(len(df))]
        
        if 'Date' not in df.columns:
            print("Adding missing 'Date' column...")
            df['Date'] = datetime.now().strftime("%Y-%m-%d")
        
        # Save updated dataframe back to CSV file
        df.to_csv("TaxTruth_Exploitation.csv", index=False)
        print("Updated CSV file with required columns")
    except Exception as e:
        print(f"Error loading TaxTruth_Exploitation dataset: {e}")
        flash(f'Error loading dataset: {str(e)}', 'danger')
        df = pd.DataFrame()
    
    # If df is empty, reset all variables and return
    if df.empty:
        print("No data available in the uploaded dataset.")
        sentiment_percentages = None
        detailed_sentiment_percentages = None
        total_comments = None
        monthly_sentiment = None
        top_keywords = None
        recent_comments = None
        comments_data = None
        all_text = None
        positive_text = None
        negative_text = None
        neutral_text = None
        ai_summaries = None
        section_sentiment = None
        all_wordcloud_base64 = None
        positive_wordcloud_base64 = None
        negative_wordcloud_base64 = None
        neutral_wordcloud_base64 = None
        highlighted_comments = None
        return
    
    # Process the data
    processed_data = process_data(df)
    df = processed_data["df"]
    sentiment_percentages = processed_data["sentiment_percentages"]
    detailed_sentiment_percentages = processed_data["detailed_sentiment_percentages"]
    total_comments = processed_data["total_comments"]
    monthly_sentiment = processed_data["monthly_sentiment"]
    top_keywords = processed_data["top_keywords"]
    recent_comments = processed_data["recent_comments"]
    comments_data = processed_data["comments_data"]
    all_text = processed_data["all_text"]
    positive_text = processed_data["positive_text"]
    negative_text = processed_data["negative_text"]
    neutral_text = processed_data["neutral_text"]
    ai_summaries = processed_data["ai_summaries"]
    section_sentiment = processed_data["section_sentiment"]
    all_wordcloud_base64 = processed_data["all_wordcloud_base64"]
    positive_wordcloud_base64 = processed_data["positive_wordcloud_base64"]
    negative_wordcloud_base64 = processed_data["negative_wordcloud_base64"]
    neutral_wordcloud_base64 = processed_data["neutral_wordcloud_base64"]
    highlighted_comments = processed_data["highlighted_comments"]
    print("Data reprocessing completed.")

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# Word Cloud Generation - Optimized to return base64 string
def generate_wordcloud_base64(text, color=None):
    if not text or len(text.strip()) == 0:
        # Create a simple image with "No data available" text
        img_buffer = io.BytesIO()
        plt.figure(figsize=(6,4), dpi=100)
        plt.text(0.5, 0.5, 'No data available', 
                 horizontalalignment='center', verticalalignment='center', 
                 transform=plt.gca().transAxes, fontsize=16)
        plt.axis('off')
        plt.tight_layout(pad=0)
        plt.savefig(img_buffer, format="png")
        plt.close()
        img_buffer.seek(0)
        return base64.b64encode(img_buffer.read()).decode('utf-8')
    
    # Set contour color based on sentiment
    contour_color = color if color else 'steelblue'
    
    # Create word cloud with optimized settings
    wc = WordCloud(
        background_color="white",
        max_words=100,  # Reduced for faster generation
        width=600,
        height=400,
        contour_width=3,
        contour_color=contour_color,
        collocations=False,  # Disable collocations for faster generation
        random_state=42  # For reproducibility
    ).generate(text)
    
    # Save to a bytes buffer
    img_buffer = io.BytesIO()
    plt.figure(figsize=(6,4), dpi=100)
    plt.imshow(wc, interpolation="bilinear")
    plt.axis("off")
    plt.tight_layout(pad=0)
    plt.savefig(img_buffer, format="png")
    plt.close()
    img_buffer.seek(0)
    
    # Return as base64 string
    return base64.b64encode(img_buffer.read()).decode('utf-8')

# Word Cloud Routes - Now serve base64 encoded images
@app.route("/wordcloud.png")
@login_required
def wordcloud_png():
    if all_wordcloud_base64:
        img_data = base64.b64decode(all_wordcloud_base64)
        return send_file(io.BytesIO(img_data), mimetype="image/png")
    else:
        # Fallback to generating on the fly
        img = generate_wordcloud_image(all_text)
        return send_file(img, mimetype="image/png")

@app.route("/positive_wordcloud.png")
@login_required
def positive_wordcloud_png():
    if positive_wordcloud_base64:
        img_data = base64.b64decode(positive_wordcloud_base64)
        return send_file(io.BytesIO(img_data), mimetype="image/png")
    else:
        # Fallback to generating on the fly
        img = generate_positive_wordcloud_image(positive_text)
        return send_file(img, mimetype="image/png")

@app.route("/negative_wordcloud.png")
@login_required
def negative_wordcloud_png():
    if negative_wordcloud_base64:
        img_data = base64.b64decode(negative_wordcloud_base64)
        return send_file(io.BytesIO(img_data), mimetype="image/png")
    else:
        # Fallback to generating on the fly
        img = generate_negative_wordcloud_image(negative_text)
        return send_file(img, mimetype="image/png")

@app.route("/neutral_wordcloud.png")
@login_required
def neutral_wordcloud_png():
    if neutral_wordcloud_base64:
        img_data = base64.b64decode(neutral_wordcloud_base64)
        return send_file(io.BytesIO(img_data), mimetype="image/png")
    else:
        # Fallback to generating on the fly
        img = generate_neutral_wordcloud_image(neutral_text)
        return send_file(img, mimetype="image/png")

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['is_admin'] = user.is_admin
            
            # For admin users, redirect to upload page if no data is available
            if user.is_admin:
                if df is None or sentiment_percentages is None:
                    flash('Please upload a dataset to access the dashboard', 'info')
                    return redirect(url_for('upload_dataset_page'))
                else:
                    return redirect(url_for('index'))
            else:
                return redirect(url_for('index'))
        else:
            flash('Invalid username or password', 'danger')
    
    return render_template_string(login_template)

# Logout route
@app.route('/logout')
def logout():
    # Clear global data variables
    global df, sentiment_percentages, detailed_sentiment_percentages, total_comments, monthly_sentiment, top_keywords, recent_comments, comments_data, all_text, positive_text, negative_text, neutral_text, ai_summaries, section_sentiment, all_wordcloud_base64, positive_wordcloud_base64, negative_wordcloud_base64, neutral_wordcloud_base64, highlighted_comments
    
    df = None
    sentiment_percentages = None
    detailed_sentiment_percentages = None
    total_comments = None
    monthly_sentiment = None
    top_keywords = None
    recent_comments = None
    comments_data = None
    all_text = None
    positive_text = None
    negative_text = None
    neutral_text = None
    ai_summaries = None
    section_sentiment = None
    all_wordcloud_base64 = None
    positive_wordcloud_base64 = None
    negative_wordcloud_base64 = None
    neutral_wordcloud_base64 = None
    highlighted_comments = None
    
    # Clear session
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

# Register route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return redirect(url_for('register'))
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'danger')
            return redirect(url_for('register'))
        
        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    
    return render_template_string(register_template)

# Comment submission route
@app.route('/submit_comment', methods=['POST'])
@login_required
def submit_comment():
    global df, sentiment_percentages, detailed_sentiment_percentages, total_comments, monthly_sentiment, top_keywords, recent_comments, comments_data, all_text, positive_text, negative_text, neutral_text, ai_summaries, section_sentiment, all_wordcloud_base64, positive_wordcloud_base64, negative_wordcloud_base64, neutral_wordcloud_base64, highlighted_comments
    
    comment_text = request.form.get('comment')
    if comment_text:
        # Analyze sentiment
        cleaned_text = preprocess(comment_text)
        sentiment = get_sentiment(cleaned_text)
        detailed_sentiment = get_detailed_sentiment(cleaned_text)
        
        # Save to database
        new_comment = UserComment(
            text=comment_text,
            sentiment=sentiment,
            detailed_sentiment=detailed_sentiment,
            user_id=session['user_id']
        )
        db.session.add(new_comment)
        db.session.commit()
        
        # Add to CSV file
        new_row = {
            "ID": len(df) + 1 if df is not None else 1,
            "PersonType": "User",
            "Profession": "General",
            "MonthlyIncome": 0,
            "TaxPaid": 0,
            "GSTItemsUsed": "",
            "GovernmentBenefit": "No",
            "BillionaireNearby": "No",
            "BillionaireTaxKnown": "₹0",
            "FeelingExploited": "Maybe",
            "PersonalComment": comment_text,
            "Location": "Online",
            "Username": session['username'],
            "Date": datetime.now().strftime("%Y-%m-%d")
        }
        
        # Load existing data
        try:
            existing_df = pd.read_csv("TaxTruth_Exploitation.csv")
        except:
            existing_df = pd.DataFrame()
        
        # Append new comment
        if not existing_df.empty:
            updated_df = pd.concat([existing_df, pd.DataFrame([new_row])], ignore_index=True)
        else:
            updated_df = pd.DataFrame([new_row])
        
        # Save back to CSV file
        updated_df.to_csv("TaxTruth_Exploitation.csv", index=False)
        
        # Reprocess data from CSV file
        reprocess_data()
        
        flash('Comment submitted successfully!', 'success')
    else:
        flash('Comment cannot be empty', 'danger')
    
    return redirect(url_for('index'))

# Debug route
@app.route("/debug")
@login_required
def debug_data():
    if not session.get('is_admin'):
        return "Access denied", 403
        
    debug_info = {
        "dataset_comments": len(df) if df is not None else 0,
        "db_comments": UserComment.query.count(),
        "total_comments_global": total_comments,
        "dataset_file_exists": os.path.exists("TaxTruth_Exploitation.csv"),
        "dataset_file_size": os.path.getsize("TaxTruth_Exploitation.csv") if os.path.exists("TaxTruth_Exploitation.csv") else 0,
        "detailed_sentiment_percentages": detailed_sentiment_percentages
    }
    
    # Try to load and verify dataset
    try:
        data = pd.read_csv("TaxTruth_Exploitation.csv")
        debug_info["dataset_file_records"] = len(data)
        
        # Check for required columns
        if not data.empty:
            sample = data.iloc[0]
            debug_info["has_comment_text"] = "Comment Text" in sample or "PersonalComment" in sample
            debug_info["has_username"] = "Username" in sample
    except Exception as e:
        debug_info["dataset_error"] = str(e)
    
    return jsonify(debug_info)

# Error handler for large files
@app.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(e):
    flash('File too large. Maximum size is 16MB.', 'danger')
    return redirect(url_for('index'))

# Function to process uploaded files
def process_uploaded_file(file_path):
    """Process uploaded dataset file in various formats"""
    file_ext = os.path.splitext(file_path)[1].lower()
    
    try:
        if file_ext == '.csv':
            df = pd.read_csv(file_path)
        elif file_ext in ['.xls', '.xlsx']:
            df = pd.read_excel(file_path)
        elif file_ext == '.json':
            df = pd.read_json(file_path)
        elif file_ext == '.tsv':
            df = pd.read_csv(file_path, sep='\t')
        else:
            raise ValueError("Unsupported file format. Please upload CSV, Excel, JSON, or TSV files.")
        
        # Check if we have a comment column
        comment_col = None
        possible_columns = ['Comment Text', 'PersonalComment', 'comment', 'text', 'comments', 'feedback', 'review']
        
        for col in possible_columns:
            if col in df.columns:
                comment_col = col
                break
        
        if comment_col is None:
            # Try to find a column that has text data
            for col in df.columns:
                if df[col].dtype == 'object':
                    # Check if it contains text (not numbers or dates)
                    sample = df[col].dropna().head(5)
                    if all(isinstance(x, str) for x in sample):
                        comment_col = col
                        break
        
        if comment_col is None:
            raise ValueError("No comment column found in the dataset. Please ensure your file has a column with text comments.")
        
        # Rename the comment column to 'Comment Text' for consistency
        df = df.rename(columns={comment_col: 'Comment Text'})
        
        # Ensure we have a 'Username' column
        if 'Username' not in df.columns:
            df['Username'] = [f"User{i+1}" for i in range(len(df))]
        
        # Ensure we have a 'Date' column
        if 'Date' not in df.columns:
            df['Date'] = datetime.now().strftime("%Y-%m-%d")
        
        return df
    except Exception as e:
        raise ValueError(f"Error processing file: {str(e)}")

# Route for uploading datasets
@app.route('/upload_dataset', methods=['POST'])
@login_required
def upload_dataset():
    if not session.get('is_admin'):
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    if 'dataset_file' not in request.files:
        flash('No file selected', 'danger')
        return redirect(url_for('upload_dataset_page'))
    
    file = request.files['dataset_file']
    if file.filename == '':
        flash('No file selected', 'danger')
        return redirect(url_for('upload_dataset_page'))
    
    if file:
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        try:
            # Process the uploaded file
            df_uploaded = process_uploaded_file(file_path)
            
            # Save the uploaded data to the main CSV file
            df_uploaded.to_csv("TaxTruth_Exploitation.csv", index=False)
            
            # Reprocess the data
            reprocess_data()
            
            flash('Dataset uploaded and processed successfully!', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            flash(f'Error processing dataset: {str(e)}', 'danger')
            return redirect(url_for('upload_dataset_page'))
    
    return redirect(url_for('upload_dataset_page'))

# Route for dataset preview
@app.route('/preview_dataset', methods=['POST'])
@login_required
def preview_dataset():
    if not session.get('is_admin'):
        return jsonify({"error": "Access denied"}), 403
    
    if 'dataset_file' not in request.files:
        return jsonify({"error": "No file selected"}), 400
    
    file = request.files['dataset_file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    
    try:
        # Save the file temporarily
        filename = secure_filename(file.filename)
        file_path = os.path.join(tempfile.gettempdir(), filename)
        file.save(file_path)
        
        # Process the uploaded file
        df_uploaded = process_uploaded_file(file_path)
        
        # Clean up temporary file
        os.remove(file_path)
        
        # Return preview data
        preview_data = {
            "columns": df_uploaded.columns.tolist(),
            "rows": df_uploaded.head(5).to_dict('records'),
            "total_rows": len(df_uploaded)
        }
        
        return jsonify(preview_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# New route for upload dataset page (GET)
@app.route('/upload_dataset_page')
@login_required
def upload_dataset_page():
    if not session.get('is_admin'):
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    # If data already exists, show dashboard
    if df is not None and sentiment_percentages is not None:
        return redirect(url_for('index'))
    
    return render_template_string(upload_prompt_template)

# Route for generating and downloading PDF report
@app.route('/generate_report')
@login_required
def generate_report():
    if not session.get('is_admin'):
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    if df is None or sentiment_percentages is None:
        flash('No data available for report generation', 'danger')
        return redirect(url_for('index'))
    
    # Create a PDF document
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    
    # Get styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        textColor=colors.darkblue
    )
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=12,
        textColor=colors.darkblue
    )
    
    # Add title
    elements.append(Paragraph("Sentiment Analysis Report", title_style))
    elements.append(Spacer(1, 12))
    
    # Add generation date
    elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
    elements.append(Spacer(1, 12))
    
    # Add summary statistics
    elements.append(Paragraph("Summary Statistics", heading_style))
    elements.append(Spacer(1, 6))
    
    stats_data = [
        ['Metric', 'Value'],
        ['Total Comments', str(total_comments)],
        ['Positive Sentiment', f"{sentiment_percentages['positive']}%"],
        ['Negative Sentiment', f"{sentiment_percentages['negative']}%"],
        ['Neutral Sentiment', f"{sentiment_percentages['neutral']}%"]
    ]
    
    stats_table = Table(stats_data, colWidths=[2*inch, 1.5*inch])
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(stats_table)
    elements.append(Spacer(1, 20))
    
    # Add detailed sentiment analysis
    elements.append(Paragraph("Detailed Sentiment Analysis", heading_style))
    elements.append(Spacer(1, 6))
    
    detailed_stats_data = [
        ['Sentiment Type', 'Percentage'],
        ['Strong Positive', f"{detailed_sentiment_percentages['strong-positive']}%"],
        ['Weak Positive', f"{detailed_sentiment_percentages['weak-positive']}%"],
        ['Weak Negative', f"{detailed_sentiment_percentages['weak-negative']}%"],
        ['Strong Negative', f"{detailed_sentiment_percentages['strong-negative']}%"]
    ]
    
    detailed_table = Table(detailed_stats_data, colWidths=[2*inch, 1.5*inch])
    detailed_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(detailed_table)
    elements.append(Spacer(1, 20))
    
    # Add abstract summary
    elements.append(Paragraph("Abstract Summary", heading_style))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph(ai_summaries['abstract'], styles['Normal']))
    elements.append(Spacer(1, 20))
    
    # Add sentiment summaries
    elements.append(Paragraph("Positive Sentiment Summary", heading_style))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph(ai_summaries['positive_summary'], styles['Normal']))
    elements.append(Spacer(1, 20))
    
    elements.append(Paragraph("Negative Sentiment Summary", heading_style))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph(ai_summaries['negative_summary'], styles['Normal']))
    elements.append(Spacer(1, 20))
    
    elements.append(Paragraph("Neutral Sentiment Summary", heading_style))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph(ai_summaries['neutral_summary'], styles['Normal']))
    elements.append(Spacer(1, 20))
    
    # Add top keywords
    elements.append(Paragraph("Top Keywords", heading_style))
    elements.append(Spacer(1, 6))
    
    keywords_text = ", ".join(top_keywords[:10])
    elements.append(Paragraph(keywords_text, styles['Normal']))
    elements.append(Spacer(1, 20))
    
    # Add word cloud images if available
    if all_wordcloud_base64:
        elements.append(Paragraph("Word Cloud - All Comments", heading_style))
        elements.append(Spacer(1, 6))
        
        # Decode base64 image and save to temporary file
        wordcloud_img = io.BytesIO(base64.b64decode(all_wordcloud_base64))
        elements.append(Image(wordcloud_img, width=5*inch, height=3.33*inch))
        elements.append(Spacer(1, 20))
    
    # Build PDF
    doc.build(elements)
    
    # Move to beginning of buffer
    buffer.seek(0)
    
    # Return PDF file
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"sentiment_analysis_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
        mimetype='application/pdf'
    )

# Upload prompt template
upload_prompt_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Upload Dataset - Sentiment Analysis</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f5f7fb;
            color: #333;
        }
        .upload-container {
            max-width: 800px;
            margin: 50px auto;
            padding: 30px;
            background-color: white;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        .header {
            background: linear-gradient(120deg, #4361ee, #3f37c9);
            color: white;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 30px;
            text-align: center;
        }
        .upload-area {
            border: 2px dashed #4361ee;
            border-radius: 10px;
            padding: 40px;
            text-align: center;
            margin-bottom: 20px;
            background-color: #f8f9ff;
        }
        .btn-primary {
            background-color: #4361ee;
            border-color: #4361ee;
        }
        .file-info {
            margin-top: 20px;
            font-size: 14px;
            color: #6c757d;
        }
    </style>
</head>
<body>
    <div class="upload-container">
        <div class="header">
            <h1><i class="fas fa-upload me-2"></i>Upload Dataset for Analysis</h1>
            <p class="mb-0">Please upload a dataset to begin sentiment analysis</p>
        </div>
        
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
                        {{ message }}
                        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        
        <div class="upload-area">
            <i class="fas fa-cloud-upload-alt fa-3x text-primary mb-3"></i>
            <h4>Upload Your Dataset</h4>
            <p class="text-muted">Supported formats: CSV, Excel, JSON, TSV (Max 16MB)</p>
            
            <form method="POST" action="{{ url_for('upload_dataset') }}" enctype="multipart/form-data">
                <div class="mb-3">
                    <input type="file" class="form-control" id="dataset_file" name="dataset_file" accept=".csv,.xls,.xlsx,.json,.tsv" required>
                </div>
                <button type="submit" class="btn btn-primary">
                    <i class="fas fa-upload me-2"></i>Upload and Process
                </button>
            </form>
            
            <div class="file-info">
                <p><strong>Note:</strong> The dataset should contain a column with text comments for sentiment analysis.</p>
                <p>After uploading, the system will analyze the sentiment of the comments and generate insights.</p>
            </div>
        </div>
        
        <div class="text-center mt-4">
            <a href="{{ url_for('logout') }}" class="btn btn-outline-secondary">
                <i class="fas fa-sign-out-alt me-1"></i> Logout
            </a>
        </div>
    </div>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

# Main HTML Template with Enhanced Dashboard
html_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sentiment Analysis Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root {
            --primary: #4361ee;
            --secondary: #3f37c9;
            --accent: #4895ef;
            --light: #f8f9fa;
            --dark: #212529;
            --success: #4cc9f0;
            --danger: #f72585;
            --warning: #ff9e00;
            --gray: #6c757d;
            --strong-positive: #2ecc71;
            --weak-positive: #3498db;
            --weak-negative: #f39c12;
            --strong-negative: #e74c3c;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f5f7fb;
            color: #333;
        }
        
        .dashboard-container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }
        
        .header {
            background: linear-gradient(120deg, var(--primary), var(--secondary));
            color: white;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        
        .card {
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
            margin-bottom: 20px;
            border: none;
            transition: transform 0.2s;
        }
        
        .card:hover {
            transform: translateY(-5px);
            box-shadow: 0 8px 15px rgba(0, 0, 0, 0.1);
        }
        
        .card-header {
            background-color: white;
            border-bottom: 1px solid #eaeaea;
            font-weight: 600;
            padding: 15px 20px;
            border-radius: 10px 10px 0 0 !important;
        }
        
        .metric-card {
            text-align: center;
            padding: 15px;
        }
        
        .metric-value {
            font-size: 24px;
            font-weight: 700;
            color: var(--primary);
        }
        
        .metric-label {
            font-size: 14px;
            color: var(--gray);
        }
        
        .positive {
            color: var(--success);
        }
        
        .negative {
            color: var(--danger);
        }
        
        .neutral {
            color: var(--gray);
        }
        
        .strong-positive {
            color: var(--strong-positive);
        }
        
        .weak-positive {
            color: var(--weak-positive);
        }
        
        .weak-negative {
            color: var(--weak-negative);
        }
        
        .strong-negative {
            color: var(--strong-negative);
        }
        
        .nav-pills .nav-link.active {
            background-color: var(--primary);
        }
        
        .btn-primary {
            background-color: var(--primary);
            border-color: var(--primary);
        }
        
        .section-title {
            border-left: 4px solid var(--primary);
            padding-left: 10px;
            margin: 20px 0 15px;
        }
        
        .search-box {
            border-radius: 20px;
            padding: 8px 20px;
            border: 1px solid #eaeaea;
        }
        
        .heat-map {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
            gap: 10px;
            margin-top: 15px;
        }
        
        .heat-item {
            padding: 10px;
            border-radius: 8px;
            text-align: center;
            background-color: #e9ecef;
            cursor: pointer;
            transition: all 0.3s;
        }
        
        .heat-item:hover {
            background-color: var(--accent);
            color: white;
        }
        
        .heat-positive {
            background-color: rgba(76, 201, 240, 0.2);
        }
        
        .heat-negative {
            background-color: rgba(247, 37, 133, 0.2);
        }
        
        .interactive-panel {
            background-color: #f8f9fa;
            border-radius: 10px;
            padding: 20px;
            margin-top: 20px;
        }
        
        .filter-options {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            margin-bottom: 15px;
        }
        
        .filter-btn {
            background-color: white;
            border: 1px solid #eaeaea;
            border-radius: 20px;
            padding: 5px 15px;
            font-size: 14px;
            cursor: pointer;
        }
        
        .filter-btn.active {
            background-color: var(--primary);
            color: white;
            border-color: var(--primary);
        }
        
        .footer {
            background: linear-gradient(120deg, var(--secondary), var(--primary));
            color: white;
            padding: 20px;
            border-radius: 10px;
            margin-top: 30px;
        }
        
        .user-avatar {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            color: white;
        }
        
        .bg-primary { background-color: var(--primary); }
        .bg-success { background-color: var(--success); }
        .bg-warning { background-color: var(--warning); }
        
        .comment-text {
            font-size: 14px;
            line-height: 1.5;
        }
        
        .sentiment-badge {
            font-size: 12px;
            padding: 3px 8px;
            border-radius: 12px;
        }
        
        .badge-positive {
            background-color: rgba(76, 201, 240, 0.2);
            color: var(--success);
        }
        
        .badge-negative {
            background-color: rgba(247, 37, 133, 0.2);
            color: var(--danger);
        }
        
        .badge-neutral {
            background-color: rgba(108, 117, 125, 0.2);
            color: var(--gray);
        }
        
        .badge-strong-positive {
            background-color: rgba(46, 204, 113, 0.2);
            color: var(--strong-positive);
        }
        
        .badge-weak-positive {
            background-color: rgba(52, 152, 219, 0.2);
            color: var(--weak-positive);
        }
        
        .badge-weak-negative {
            background-color: rgba(243, 156, 18, 0.2);
            color: var(--weak-negative);
        }
        
        .badge-strong-negative {
            background-color: rgba(231, 76, 60, 0.2);
            color: var(--strong-negative);
        }
        
        .comment-form {
            background-color: #f8f9fa;
            border-radius: 10px;
            padding: 20px;
            margin: 20px 0;
        }
        
        .ai-summary {
            background-color: #f8f9fa;
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 15px;
            border-left: 4px solid var(--primary);
        }
        
        .ai-summary-title {
            font-weight: 600;
            margin-bottom: 10px;
            color: var(--primary);
        }
        
        .ai-icon {
            color: var(--primary);
            margin-right: 8px;
        }
        
        .wordcloud-container {
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
            background-color: #f8f9fa;
            border-radius: 10px;
            margin-top: 20px;
        }
        
        .chart-container {
            position: relative;
            height: 300px;
            width: 100%;
        }
        
        .detailed-chart-container {
            position: relative;
            height: 250px;
            width: 100%;
        }
        
        .username {
            font-weight: 600;
            color: var(--primary);
        }
        
        .section-comment {
            font-size: 12px;
            padding: 5px;
            margin-bottom: 5px;
            border-radius: 5px;
            background-color: rgba(0,0,0,0.05);
        }
        
        .loading-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(255, 255, 255, 0.8);
            display: flex;
            justify-content: center;
            align-items: center;
            z-index: 9999;
        }
        
        .loading-spinner {
            border: 5px solid #f3f3f3;
            border-top: 5px solid var(--primary);
            border-radius: 50%;
            width: 50px;
            height: 50px;
            animation: spin 1s linear infinite;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .tab-container {
            margin-bottom: 20px;
        }
        
        .detailed-sentiment-legend {
            display: flex;
            justify-content: center;
            flex-wrap: wrap;
            gap: 15px;
            margin-top: 10px;
        }
        
        .legend-item {
            display: flex;
            align-items: center;
            font-size: 14px;
        }
        
        .legend-color {
            width: 16px;
            height: 16px;
            border-radius: 4px;
            margin-right: 6px;
        }
        
        .nav-link {
            color: var(--primary);
        }
        
        .nav-link:hover {
            color: var(--secondary);
        }
        
        .nav-link.active {
            color: white;
        }
        
        .abstract-summary {
            font-size: 16px;
            line-height: 1.6;
            text-align: justify;
        }
        
        .sentiment-summary {
            font-size: 15px;
            line-height: 1.5;
            text-align: justify;
        }
        
        .wordcloud-tabs {
            display: flex;
            justify-content: center;
            margin-bottom: 15px;
        }
        
        .wordcloud-tab {
            padding: 8px 16px;
            margin: 0 5px;
            border-radius: 20px 20px 0 0;
            background-color: #e9ecef;
            cursor: pointer;
            transition: all 0.3s;
        }
        
        .wordcloud-tab.active {
            background-color: var(--primary);
            color: white;
        }
        
        .wordcloud-content {
            display: none;
        }
        
        .wordcloud-content.active {
            display: block;
        }
        
        .report-button {
            position: fixed;
            bottom: 20px;
            right: 20px;
            z-index: 1000;
            background-color: var(--primary);
            color: white;
            border-radius: 50%;
            width: 60px;
            height: 60px;
            display: flex;
            justify-content: center;
            align-items: center;
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
            transition: all 0.3s;
        }
        
        .report-button:hover {
            transform: scale(1.1);
            background-color: var(--secondary);
        }
        
        .comments-section {
            margin-top: 20px;
        }
        
        .comment-item {
            margin-bottom: 15px;
            padding: 15px;
            border-radius: 8px;
            background-color: #f8f9fa;
            border-left: 4px solid var(--primary);
        }
        
        .comment-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
        }
        
        .comment-meta {
            font-size: 12px;
            color: var(--gray);
        }
        
        .comment-content {
            font-size: 14px;
            line-height: 1.5;
        }
        
        .comment-content u {
            color: var(--primary);
            font-weight: 500;
        }
        
        .pagination-container {
            display: flex;
            justify-content: center;
            margin-top: 20px;
        }
        
        .highlighted-keyword {
            color: var(--primary);
            font-weight: 500;
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <div class="dashboard-container">
        <div class="header">
            <div class="row align-items-center">
                <div class="col-md-6">
                    <h1><i class="fas fa-chart-pie me-2"></i>Sentiment Analysis</h1>
                    <p class="mb-0">Analyzing public sentiment for insights and trends</p>
                </div>
                <div class="col-md-6 text-end">
                    <div class="d-flex justify-content-end gap-2">
                        {% if 'user_id' in session %}
                            <span class="text-white me-2">Welcome, {{ session.username }}</span>
                            {% if session.is_admin %}
                                <a href="{{ url_for('generate_report') }}" class="btn btn-light" title="Generate PDF Report">
                                    <i class="fas fa-file-pdf me-1"></i> Report
                                </a>
                            {% endif %}
                            <a href="{{ url_for('logout') }}" class="btn btn-light"><i class="fas fa-sign-out-alt me-1"></i> Logout</a>
                        {% else %}
                            <a href="{{ url_for('login') }}" class="btn btn-light"><i class="fas fa-user me-1"></i> Login</a>
                        {% endif %}
                    </div>
                </div>
            </div>
        </div>
        
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
                        {{ message }}
                        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        
        {% if 'user_id' in session and not session.is_admin %}
        <div class="comment-form">
            <h5><i class="fas fa-comment me-2"></i>Submit Your Feedback</h5>
            <form method="POST" action="{{ url_for('submit_comment') }}">
                <div class="mb-3">
                    <textarea class="form-control" name="comment" rows="3" placeholder="Enter your comment here..." required></textarea>
                </div>
                <button type="submit" class="btn btn-primary">Submit Comment</button>
            </form>
        </div>
        {% elif 'user_id' not in session %}
        <div class="alert alert-info">
            <h4><i class="fas fa-info-circle me-2"></i>Access Restricted</h4>
            <p>Please log in to access the dashboard.</p>
        </div>
        {% endif %}
        
        {% if 'user_id' in session and session.is_admin %}
        <div class="row">
            <div class="col-md-8">
                <div class="card">
                    <div class="card-header">
                        <span><i class="fas fa-chart-bar me-2"></i>Feedback Analysis Overview</span>
                    </div>
                    <div class="card-body">
                        <ul class="nav nav-pills mb-3" id="sentimentTabs" role="tablist">
                            <li class="nav-item" role="presentation">
                                <button class="nav-link active" id="basic-tab" data-bs-toggle="pill" data-bs-target="#basic" type="button" role="tab" aria-controls="basic" aria-selected="true">Basic Sentiment</button>
                            </li>
                            <li class="nav-item" role="presentation">
                                <button class="nav-link" id="detailed-tab" data-bs-toggle="pill" data-bs-target="#detailed" type="button" role="tab" aria-controls="detailed" aria-selected="false">Detailed Sentiment</button>
                            </li>
                        </ul>
                        <div class="tab-content" id="sentimentTabsContent">
                            <div class="tab-pane fade show active" id="basic" role="tabpanel" aria-labelledby="basic-tab">
                                <div class="chart-container">
                                    <canvas id="sentimentChart"></canvas>
                                </div>
                            </div>
                            <div class="tab-pane fade" id="detailed" role="tabpanel" aria-labelledby="detailed-tab">
                                <div class="detailed-chart-container">
                                    <canvas id="detailedSentimentChart"></canvas>
                                </div>
                                <div class="detailed-sentiment-legend">
                                    <div class="legend-item">
                                        <div class="legend-color" style="background-color: var(--strong-positive);"></div>
                                        <span>Strong Positive</span>
                                    </div>
                                    <div class="legend-item">
                                        <div class="legend-color" style="background-color: var(--weak-positive);"></div>
                                        <span>Weak Positive</span>
                                    </div>
                                    <div class="legend-item">
                                        <div class="legend-color" style="background-color: var(--weak-negative);"></div>
                                        <span>Weak Negative</span>
                                    </div>
                                    <div class="legend-item">
                                        <div class="legend-color" style="background-color: var(--strong-negative);"></div>
                                        <span>Strong Negative</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="card">
                    <div class="card-header">
                        <i class="fas fa-map me-2"></i>Section Heat Map - Sentiment Analysis</i>
                    </div>
                    <div class="card-body">
                        <div class="heat-map">
                            <div class="heat-item heat-positive" data-section="A1: Centralization">A1: Centralization</div>
                            <div class="heat-item heat-negative" data-section="A2: Compliance">A2: Compliance</div>
                            <div class="heat-item heat-positive" data-section="A3: Transparency">A3: Transparency</div>
                            <div class="heat-item" data-section="B1: Implementation">B1: Implementation</div>
                            <div class="heat-item heat-negative" data-section="B2: Regulation">B2: Regulation</div>
                            <div class="heat-item" data-section="B3: Accountability">B3: Accountability</div>
                            <div class="heat-item heat-positive" data-section="C1: Data Rights">C1: Data Rights</div>
                            <div class="heat-item" data-section="C2: Security">C2: Security</div>
                            <div class="heat-item heat-negative" data-section="C3: Enforcement">C3: Enforcement</div>
                            <div class="heat-item" data-section="D1: Oversight">D1: Oversight</div>
                            <div class="heat-item heat-positive" data-section="D2: User Control">D2: User Control</div>
                            <div class="heat-item" data-section="D3: Breach Notification">D3: Breach Notification</div>
                        </div>
                        
                        <div class="interactive-panel">
                            <h5><i class="fas fa-info-circle me-2"></i>Section Details: <span id="selected-section">A1: Centralization</span></h5>
                            <div class="row mt-3">
                                <div class="col-md-6">
                                    <div class="card">
                                        <div class="card-body">
                                            <h6>Sentiment Distribution</h6>
                                            <canvas id="sectionChart" height="150"></canvas>
                                        </div>
                                    </div>
                                </div>
                                <div class="col-md-6">
                                    <div class="card">
                                        <div class="card-body">
                                            <h6>Key Metrics</h6>
                                            <div class="d-flex justify-content-between mb-2">
                                                <span>Positive:</span>
                                                <span class="positive" id="detail-positive">68%</span>
                                            </div>
                                            <div class="d-flex justify-content-between mb-2">
                                                <span>Negative:</span>
                                                <span class="negative" id="detail-negative">15%</span>
                                            </div>
                                            <div class="d-flex justify-content-between mb-2">
                                                <span>Neutral:</span>
                                                <span class="neutral" id="detail-neutral">17%</span>
                                            </div>
                                            <div class="d-flex justify-content-between mb-2">
                                                <span>Total Comments:</span>
                                                <span id="detail-total">142</span>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            
                            <div class="mt-3">
                                <h6>Detailed Sentiment Breakdown</h6>
                                <div class="row">
                                    <div class="col-3">
                                        <div class="text-center">
                                            <div class="metric-value strong-positive" id="detail-strong-positive">25%</div>
                                            <div class="metric-label">Strong Positive</div>
                                        </div>
                                    </div>
                                    <div class="col-3">
                                        <div class="text-center">
                                            <div class="metric-value weak-positive" id="detail-weak-positive">25%</div>
                                            <div class="metric-label">Weak Positive</div>
                                        </div>
                                    </div>
                                    <div class="col-3">
                                        <div class="text-center">
                                            <div class="metric-value weak-negative" id="detail-weak-negative">25%</div>
                                            <div class="metric-label">Weak Negative</div>
                                        </div>
                                    </div>
                                    <div class="col-3">
                                        <div class="text-center">
                                            <div class="metric-value strong-negative" id="detail-strong-negative">25%</div>
                                            <div class="metric-label">Strong Negative</div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            
                            <div class="mt-3">
                                <h6>Sample Comments</h6>
                                <div id="section-comments">
                                    <!-- Comments will be populated by JavaScript -->
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="card">
                    <div class="card-header">
                        <i class="fas fa-cloud me-2"></i>Sentiment Word Clouds</i>
                    </div>
                    <div class="card-body">
                        <div class="wordcloud-tabs">
                            <div class="wordcloud-tab active" onclick="showWordcloud('all')">All Comments</div>
                            <div class="wordcloud-tab" onclick="showWordcloud('positive')">Positive</div>
                            <div class="wordcloud-tab" onclick="showWordcloud('negative')">Negative</div>
                            <div class="wordcloud-tab" onclick="showWordcloud('neutral')">Neutral</div>
                        </div>
                        
                        <div id="all-wordcloud" class="wordcloud-content active">
                            <div class="wordcloud-container">
                                <img src="data:image/png;base64,{{ all_wordcloud_base64 }}" alt="All Comments Word Cloud" class="img-fluid rounded">
                            </div>
                        </div>
                        
                        <div id="positive-wordcloud" class="wordcloud-content">
                            <div class="wordcloud-container">
                                <img src="data:image/png;base64,{{ positive_wordcloud_base64 }}" alt="Positive Comments Word Cloud" class="img-fluid rounded">
                            </div>
                        </div>
                        
                        <div id="negative-wordcloud" class="wordcloud-content">
                            <div class="wordcloud-container">
                                <img src="data:image/png;base64,{{ negative_wordcloud_base64 }}" alt="Negative Comments Word Cloud" class="img-fluid rounded">
                            </div>
                        </div>
                        
                        <div id="neutral-wordcloud" class="wordcloud-content">
                            <div class="wordcloud-container">
                                <img src="data:image/png;base64,{{ neutral_wordcloud_base64 }}" alt="Neutral Comments Word Cloud" class="img-fluid rounded">
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="card comments-section">
                    <div class="card-header">
                        <i class="fas fa-comments me-2"></i>All Comments with Important Keywords</i>
                    </div>
                    <div class="card-body">
                        <div class="mb-3">
                            <div class="d-flex justify-content-between align-items-center">
                                <div class="filter-options">
                                    <button class="filter-btn active" onclick="filterComments('all')">All</button>
                                    <button class="filter-btn" onclick="filterComments('positive')">Positive</button>
                                    <button class="filter-btn" onclick="filterComments('negative')">Negative</button>
                                    <button class="filter-btn" onclick="filterComments('neutral')">Neutral</button>
                                </div>
                                <div class="text-muted">
                                    <i class="fas fa-info-circle me-1"></i> Important keywords are underlined
                                </div>
                            </div>
                        </div>
                        
                        <div id="comments-container">
                            {% for comment in highlighted_comments %}
                            <div class="comment-item" data-sentiment="{{ comment.sentiment }}">
                                <div class="comment-header">
                                    <div>
                                        <strong class="username">{{ comment.Username }}</strong>
                                        <span class="comment-meta">{{ comment.sentiment|capitalize }}</span>
                                        {% if comment.detailed_sentiment %}
                                        <span class="comment-meta">
                                            {% if comment.detailed_sentiment == 'strong-positive' %}Strong Positive{% elif comment.detailed_sentiment == 'weak-positive' %}Weak Positive{% elif comment.detailed_sentiment == 'weak-negative' %}Weak Negative{% else %}Strong Negative{% endif %}
                                        </span>
                                        {% endif %}
                                    </div>
                                </div>
                                <div class="comment-content">
                                    {{ comment['Comment Text']|safe }}
                                </div>
                            </div>
                            {% endfor %}
                        </div>
                        
                        <div class="pagination-container">
                            <nav aria-label="Comments pagination">
                                <ul class="pagination">
                                    <li class="page-item disabled">
                                        <a class="page-link" href="#" tabindex="-1" aria-disabled="true">Previous</a>
                                    </li>
                                    <li class="page-item active"><a class="page-link" href="#">1</a></li>
                                    <li class="page-item"><a class="page-link" href="#">2</a></li>
                                    <li class="page-item"><a class="page-link" href="#">3</a></li>
                                    <li class="page-item">
                                        <a class="page-link" href="#">Next</a>
                                    </li>
                                </ul>
                            </nav>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="col-md-4">
                <div class="card">
                    <div class="card-header">
                        <i class="fas fa-chart-line me-2"></i>Summary Metrics</i>
                    </div>
                    <div class="card-body">
                        <div class="row">
                            <div class="col-6 mb-3">
                                <div class="metric-card">
                                    <div class="metric-value positive">{{ sentiment_percentages.positive }}%</div>
                                    <div class="metric-label">Positive Sentiment</div>
                                </div>
                            </div>
                            <div class="col-6 mb-3">
                                <div class="metric-card">
                                    <div class="metric-value negative">{{ sentiment_percentages.negative }}%</div>
                                    <div class="metric-label">Negative Sentiment</div>
                                </div>
                            </div>
                            <div class="col-6 mb-3">
                                <div class="metric-card">
                                    <div class="metric-value neutral">{{ sentiment_percentages.neutral }}%</div>
                                    <div class="metric-label">Neutral Sentiment</div>
                                </div>
                            </div>
                            <div class="col-6 mb-3">
                                <div class="metric-card">
                                    <div class="metric-value">{{ total_comments }}</div>
                                    <div class="metric-label">Total Comments</div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="card">
                    <div class="card-header">
                        <i class="fas fa-file-alt me-2"></i>Abstract Summary</i>
                    </div>
                    <div class="card-body">
                        <div class="ai-summary">
                            <div class="ai-summary-title"><i class="fas fa-magic ai-icon"></i>Analysis Overview</div>
                            <p class="abstract-summary">{{ ai_summaries.abstract }}</p>
                        </div>
                    </div>
                </div>
                
                <div class="card">
                    <div class="card-header">
                        <i class="fas fa-smile me-2"></i>Positive Sentiment Summary</i>
                    </div>
                    <div class="card-body">
                        <div class="ai-summary">
                            <div class="ai-summary-title"><i class="fas fa-thumbs-up ai-icon"></i>Positive Insights</div>
                            <p class="sentiment-summary">{{ ai_summaries.positive_summary }}</p>
                        </div>
                    </div>
                </div>
                
                <div class="card">
                    <div class="card-header">
                        <i class="fas fa-frown me-2"></i>Negative Sentiment Summary</i>
                    </div>
                    <div class="card-body">
                        <div class="ai-summary">
                            <div class="ai-summary-title"><i class="fas fa-thumbs-down ai-icon"></i>Negative Insights</div>
                            <p class="sentiment-summary">{{ ai_summaries.negative_summary }}</p>
                        </div>
                    </div>
                </div>
                
                <div class="card">
                    <div class="card-header">
                        <i class="fas fa-meh me-2"></i>Neutral Sentiment Summary</i>
                    </div>
                    <div class="card-body">
                        <div class="ai-summary">
                            <div class="ai-summary-title"><i class="fas fa-balance-scale ai-icon"></i>Neutral Insights</div>
                            <p class="sentiment-summary">{{ ai_summaries.neutral_summary }}</p>
                        </div>
                    </div>
                </div>
                
                <div class="card">
                    <div class="card-header">
                        <i class="fas fa-key me-2"></i>Top Keywords</i>
                    </div>
                    <div class="card-body">
                        <div class="d-flex flex-wrap gap-2">
                            {% for keyword in top_keywords %}
                            <span class="badge bg-primary">{{ keyword }}</span>
                            {% endfor %}
                        </div>
                    </div>
                </div>
                
                <div class="card">
                    <div class="card-header">
                        <i class="fas fa-comments me-2"></i>Recent Comments</i>
                    </div>
                    <div class="card-body">
                        {% for comment in recent_comments %}
                        <div class="d-flex align-items-start mb-3">
                            <div class="me-3">
                                <div class="user-avatar bg-primary">{{ comment.Username[0].upper() }}</div>
                            </div>
                            <div class="flex-grow-1">
                                <strong class="username">{{ comment.Username }}</strong>
                                <p class="comment-text mb-1">{{ comment['Comment Text'][:80] }}{% if comment['Comment Text']|length > 80 %}...{% endif %}</p>
                                <div>
                                    <span class="sentiment-badge {% if comment.sentiment == 'positive' %}badge-positive{% elif comment.sentiment == 'negative' %}badge-negative{% else %}badge-neutral{% endif %}">
                                        {{ comment.sentiment|capitalize }}
                                    </span>
                                    {% if comment.detailed_sentiment %}
                                    <span class="sentiment-badge {% if comment.detailed_sentiment == 'strong-positive' %}badge-strong-positive{% elif comment.detailed_sentiment == 'weak-positive' %}badge-weak-positive{% elif comment.detailed_sentiment == 'weak-negative' %}badge-weak-negative{% else %}badge-strong-negative{% endif %}">
                                        {% if comment.detailed_sentiment == 'strong-positive' %}Strong Positive{% elif comment.detailed_sentiment == 'weak-positive' %}Weak Positive{% elif comment.detailed_sentiment == 'weak-negative' %}Weak Negative{% else %}Strong Negative{% endif %}
                                    </span>
                                    {% endif %}
                                </div>
                            </div>
                        </div>
                        {% endfor %}
                    </div>
                </div>
            </div>
        </div>
        {% endif %}
        
        <div class="footer">
            <div class="row">
                <div class="col-md-6">
                    <h5><i class="fas fa-coins me-2"></i>Sentiment Analysis</h5>
                    <p>Analyzing public sentiment for insights and trends</p>
                </div>
                <div class="col-md-6">
                    <h5><i class="fas fa-info-circle me-2"></i>About</h5>
                    <p>This dashboard analyzes sentiment from the dataset to understand public perception.</p>
                </div>
            </div>
        </div>
    </div>

    <!-- Preview Modal -->
    <div class="modal fade" id="previewModal" tabindex="-1" aria-labelledby="previewModalLabel" aria-hidden="true">
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title" id="previewModalLabel">Dataset Preview</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body">
                    <div class="table-responsive">
                        <table class="table table-striped">
                            <thead id="modal-preview-header"></thead>
                            <tbody id="modal-preview-body"></tbody>
                        </table>
                    </div>
                    <div id="modal-preview-info" class="mt-2"></div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                    <button type="button" class="btn btn-primary" id="confirm-upload">Confirm Upload</button>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        {% if 'user_id' in session and session.is_admin %}
        // Section sentiment data from Python
        const sectionSentimentData = {
            {% for section, data in section_sentiment.items() %}
            "{{ section }}": {
                "positive": {{ data.positive }},
                "negative": {{ data.negative }},
                "neutral": {{ data.neutral }},
                "detailed": {
                    "strong-positive": {{ data.detailed["strong-positive"] }},
                    "weak-positive": {{ data.detailed["weak-positive"] }},
                    "weak-negative": {{ data.detailed["weak-negative"] }},
                    "strong-negative": {{ data.detailed["strong-negative"] }}
                },
                "total": {{ data.total }},
                "comments": {{ data.comments|tojson }}
            },
            {% endfor %}
        };
        
        // Main Sentiment Chart
        const ctx = document.getElementById('sentimentChart').getContext('2d');
        const sentimentChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: ['Positive', 'Negative', 'Neutral'],
                datasets: [{
                    label: 'Sentiment Distribution',
                    data: [
                        {{ sentiment_percentages.positive }},
                        {{ sentiment_percentages.negative }},
                        {{ sentiment_percentages.neutral }}
                    ],
                    backgroundColor: [
                        'rgba(76, 201, 240, 0.8)',
                        'rgba(247, 37, 133, 0.8)',
                        'rgba(108, 117, 125, 0.8)'
                    ],
                    borderColor: [
                        'rgba(76, 201, 240, 1)',
                        'rgba(247, 37, 133, 1)',
                        'rgba(108, 117, 125, 1)'
                    ],
                    borderWidth: 2,
                    borderRadius: 10,
                    barThickness: 60
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: 'Overall Sentiment Analysis',
                        font: {
                            size: 18,
                            weight: 'bold'
                        },
                        padding: {
                            top: 10,
                            bottom: 30
                        }
                    },
                    legend: {
                        display: false
                    },
                    tooltip: {
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        titleFont: {
                            size: 14,
                            weight: 'bold'
                        },
                        bodyFont: {
                            size: 13
                        },
                        padding: 12,
                        cornerRadius: 8,
                        callbacks: {
                            label: function(context) {
                                return context.parsed.y + '%';
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        ticks: {
                            callback: function(value) {
                                return value + '%';
                            },
                            font: {
                                weight: 'bold'
                            }
                        },
                        grid: {
                            color: 'rgba(0, 0, 0, 0.05)'
                        }
                    },
                    x: {
                        grid: {
                            display: false
                        },
                        ticks: {
                            font: {
                                weight: 'bold',
                                size: 14
                            }
                        }
                    }
                },
                animation: {
                    duration: 2000,
                    easing: 'easeOutBounce'
                }
            }
        });
        
        // Detailed Sentiment Chart
        const detailedCtx = document.getElementById('detailedSentimentChart').getContext('2d');
        const detailedSentimentChart = new Chart(detailedCtx, {
            type: 'bar',
            data: {
                labels: ['Strong Positive', 'Weak Positive', 'Weak Negative', 'Strong Negative'],
                datasets: [{
                    label: 'Detailed Sentiment Distribution',
                    data: [
                        {{ detailed_sentiment_percentages["strong-positive"] }},
                        {{ detailed_sentiment_percentages["weak-positive"] }},
                        {{ detailed_sentiment_percentages["weak-negative"] }},
                        {{ detailed_sentiment_percentages["strong-negative"] }}
                    ],
                    backgroundColor: [
                        'rgba(46, 204, 113, 0.8)',
                        'rgba(52, 152, 219, 0.8)',
                        'rgba(243, 156, 18, 0.8)',
                        'rgba(231, 76, 60, 0.8)'
                    ],
                    borderColor: [
                        'rgba(46, 204, 113, 1)',
                        'rgba(52, 152, 219, 1)',
                        'rgba(243, 156, 18, 1)',
                        'rgba(231, 76, 60, 1)'
                    ],
                    borderWidth: 2,
                    borderRadius: 10,
                    barThickness: 50
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: 'Detailed Sentiment Analysis',
                        font: {
                            size: 18,
                            weight: 'bold'
                        },
                        padding: {
                            top: 10,
                            bottom: 30
                        }
                    },
                    legend: {
                        display: false
                    },
                    tooltip: {
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        titleFont: {
                            size: 14,
                            weight: 'bold'
                        },
                        bodyFont: {
                            size: 13
                        },
                        padding: 12,
                        cornerRadius: 8,
                        callbacks: {
                            label: function(context) {
                                return context.parsed.y + '%';
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        ticks: {
                            callback: function(value) {
                                return value + '%';
                            },
                            font: {
                                weight: 'bold'
                            }
                        },
                        grid: {
                            color: 'rgba(0, 0, 0, 0.05)'
                        }
                    },
                    x: {
                        grid: {
                            display: false
                        },
                        ticks: {
                            font: {
                                weight: 'bold',
                                size: 12
                            }
                        }
                    }
                },
                animation: {
                    duration: 2000,
                    easing: 'easeOutBounce'
                }
            }
        });
        
        // Section Chart
        const sectCtx = document.getElementById('sectionChart').getContext('2d');
        const sectionChart = new Chart(sectCtx, {
            type: 'doughnut',
            data: {
                labels: ['Positive', 'Negative', 'Neutral'],
                datasets: [{
                    data: [68, 15, 17],
                    backgroundColor: [
                        '#4cc9f0',
                        '#f72585',
                        '#6c757d'
                    ],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                cutout: '70%',
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        });
        
        // Function to update section details
        function updateSectionDetails(sectionName) {
            const sectionData = sectionSentimentData[sectionName];
            
            // Update detail metrics
            document.getElementById('detail-positive').textContent = sectionData.positive + '%';
            document.getElementById('detail-negative').textContent = sectionData.negative + '%';
            document.getElementById('detail-neutral').textContent = sectionData.neutral + '%';
            document.getElementById('detail-total').textContent = sectionData.total;
            
            // Update detailed sentiment metrics
            document.getElementById('detail-strong-positive').textContent = sectionData.detailed["strong-positive"] + '%';
            document.getElementById('detail-weak-positive').textContent = sectionData.detailed["weak-positive"] + '%';
            document.getElementById('detail-weak-negative').textContent = sectionData.detailed["weak-negative"] + '%';
            document.getElementById('detail-strong-negative').textContent = sectionData.detailed["strong-negative"] + '%';
            
            // Update section chart
            sectionChart.data.datasets[0].data = [
                sectionData.positive,
                sectionData.negative,
                sectionData.neutral
            ];
            sectionChart.update();
            
            // Update sample comments
            const commentsContainer = document.getElementById('section-comments');
            commentsContainer.innerHTML = '';
            
            if (sectionData.comments.length > 0) {
                sectionData.comments.forEach(comment => {
                    const commentDiv = document.createElement('div');
                    commentDiv.className = 'section-comment';
                    
                    const sentimentClass = comment.sentiment === 'positive' ? 'badge-positive' : 
                                          comment.sentiment === 'negative' ? 'badge-negative' : 'badge-neutral';
                    
                    let detailedSentimentHtml = '';
                    if (comment.detailed_sentiment) {
                        const detailedSentimentClass = 
                            comment.detailed_sentiment === 'strong-positive' ? 'badge-strong-positive' :
                            comment.detailed_sentiment === 'weak-positive' ? 'badge-weak-positive' :
                            comment.detailed_sentiment === 'weak-negative' ? 'badge-weak-negative' : 'badge-strong-negative';
                        
                        const detailedSentimentText = 
                            comment.detailed_sentiment === 'strong-positive' ? 'Strong Positive' :
                            comment.detailed_sentiment === 'weak-positive' ? 'Weak Positive' :
                            comment.detailed_sentiment === 'weak-negative' ? 'Weak Negative' : 'Strong Negative';
                        
                        detailedSentimentHtml = `<span class="sentiment-badge ${detailedSentimentClass}">${detailedSentimentText}</span>`;
                    }
                    
                    commentDiv.innerHTML = `
                        <strong>${comment.Username}:</strong> ${comment['Comment Text'].substring(0, 80)}${comment['Comment Text'].length > 80 ? '...' : ''}
                        <span class="sentiment-badge ${sentimentClass}">${comment.sentiment}</span>
                        ${detailedSentimentHtml}
                    `;
                    
                    commentsContainer.appendChild(commentDiv);
                });
            } else {
                commentsContainer.innerHTML = '<p class="text-muted">No comments found for this section.</p>';
            }
        }
        
        // Initialize with first section
        updateSectionDetails('A1: Centralization');
        
        // Heat map interaction
        document.querySelectorAll('.heat-item').forEach(item => {
            item.addEventListener('click', function() {
                const sectionName = this.getAttribute('data-section');
                document.getElementById('selected-section').textContent = sectionName;
                updateSectionDetails(sectionName);
            });
        });
        
        // Word cloud tab switching
        function showWordcloud(type) {
            // Hide all word clouds
            document.querySelectorAll('.wordcloud-content').forEach(content => {
                content.classList.remove('active');
            });
            
            // Remove active class from all tabs
            document.querySelectorAll('.wordcloud-tab').forEach(tab => {
                tab.classList.remove('active');
            });
            
            // Show selected word cloud
            document.getElementById(type + '-wordcloud').classList.add('active');
            
            // Add active class to selected tab
            event.target.classList.add('active');
        }
        
        // Filter comments function
        function filterComments(sentiment) {
            // Update active filter button
            document.querySelectorAll('.filter-btn').forEach(btn => {
                btn.classList.remove('active');
            });
            event.target.classList.add('active');
            
            // Show/hide comments based on sentiment
            const commentItems = document.querySelectorAll('.comment-item');
            commentItems.forEach(item => {
                if (sentiment === 'all' || item.getAttribute('data-sentiment') === sentiment) {
                    item.style.display = 'block';
                } else {
                    item.style.display = 'none';
                }
            });
        }
        {% endif %}
    </script>
</body>
</html>
"""

# Login template - Updated to remove "submit feedback" phrase
login_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - Sentiment Analysis</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        body {
            background-color: #f5f7fb;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            height: 100vh;
            display: flex;
            align-items: center;
        }
        .login-container {
            max-width: 400px;
            width: 100%;
            padding: 20px;
        }
        .card {
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        .card-header {
            background: linear-gradient(120deg, #4361ee, #3f37c9);
            color: white;
            border-radius: 10px 10px 0 0 !important;
            text-align: center;
            padding: 20px;
        }
        .btn-primary {
            background-color: #4361ee;
            border-color: #4361ee;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="row justify-content-center">
            <div class="col-md-6 login-container">
                <div class="card">
                    <div class="card-header">
                        <h4><i class="fas fa-sign-in-alt me-2"></i>Login</h4>
                    </div>
                    <div class="card-body">
                        {% with messages = get_flashed_messages(with_categories=true) %}
                            {% if messages %}
                                {% for category, message in messages %}
                                    <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
                                        {{ message }}
                                        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                                    </div>
                                {% endfor %}
                            {% endif %}
                        {% endwith %}
                        
                        <form method="POST">
                            <div class="mb-3">
                                <label for="username" class="form-label">Username</label>
                                <input type="text" class="form-control" id="username" name="username" required>
                            </div>
                            <div class="mb-3">
                                <label for="password" class="form-label">Password</label>
                                <input type="password" class="form-control" id="password" name="password" required>
                            </div>
                            <button type="submit" class="btn btn-primary w-100">Login</button>
                        </form>
                        
                        <div class="text-center mt-3">
                            <p><a href="{{ url_for('index') }}">Back to homepage</a></p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

# Register template - Updated title
register_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Register - Sentiment Analysis</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        body {
            background-color: #f5f7fb;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            height: 100vh;
            display: flex;
            align-items: center;
        }
        .register-container {
            max-width: 400px;
            width: 100%;
            padding: 20px;
        }
        .card {
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        .card-header {
            background: linear-gradient(120deg, #4361ee, #3f37c9);
            color: white;
            border-radius: 10px 10px 0 0 !important;
            text-align: center;
            padding: 20px;
        }
        .btn-primary {
            background-color: #4361ee;
            border-color: #4361ee;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="row justify-content-center">
            <div class="col-md-6 register-container">
                <div class="card">
                    <div class="card-header">
                        <h4><i class="fas fa-user-plus me-2"></i>Register</h4>
                    </div>
                    <div class="card-body">
                        {% with messages = get_flashed_messages(with_categories=true) %}
                            {% if messages %}
                                {% for category, message in messages %}
                                    <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
                                        {{ message }}
                                        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                                    </div>
                                {% endfor %}
                            {% endif %}
                        {% endwith %}
                        
                        <form method="POST">
                            <div class="mb-3">
                                <label for="username" class="form-label">Username</label>
                                <input type="text" class="form-control" id="username" name="username" required>
                            </div>
                            <div class="mb-3">
                                <label for="password" class="form-label">Password</label>
                                <input type="password" class="form-control" id="password" name="password" required>
                            </div>
                            <div class="mb-3">
                                <label for="confirm_password" class="form-label">Confirm Password</label>
                                <input type="password" class="form-control" id="confirm_password" name="confirm_password" required>
                            </div>
                            <button type="submit" class="btn btn-primary w-100">Register</button>
                        </form>
                        
                        <div class="text-center mt-3">
                            <p>Already have an account? <a href="{{ url_for('login') }}">Login here</a></p>
                            <p><a href="{{ url_for('index') }}">Back to homepage</a></p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

@app.route("/")
def index():
    # Check if user has been logged out
    if 'logout_message' in session:
        logout_message = session.pop('logout_message')
        return render_template_string(logout_template, logout_message=logout_message)
    
    is_admin = session.get('is_admin', False)
    
    if is_admin:
        # If admin hasn't uploaded data, redirect to upload page
        if df is None or sentiment_percentages is None:
            return redirect(url_for('upload_dataset_page'))
        else:
            # Show full dashboard if data is available
            return render_template_string(html_template, 
                                         sentiment_percentages=sentiment_percentages,
                                         detailed_sentiment_percentages=detailed_sentiment_percentages,
                                         total_comments=total_comments,
                                         top_keywords=top_keywords,
                                         recent_comments=recent_comments,
                                         monthly_sentiment=monthly_sentiment,
                                         ai_summaries=ai_summaries,
                                         section_sentiment=section_sentiment,
                                         all_wordcloud_base64=all_wordcloud_base64,
                                         positive_wordcloud_base64=positive_wordcloud_base64,
                                         negative_wordcloud_base64=negative_wordcloud_base64,
                                         neutral_wordcloud_base64=neutral_wordcloud_base64,
                                         highlighted_comments=highlighted_comments)
    else:
        # Regular user view
        return render_template_string(html_template, 
                                     sentiment_percentages=None,
                                     detailed_sentiment_percentages=None,
                                     total_comments=None,
                                     top_keywords=None,
                                     recent_comments=None,
                                     monthly_sentiment=None,
                                     ai_summaries=None,
                                     section_sentiment=None,
                                     all_wordcloud_base64=None,
                                     positive_wordcloud_base64=None,
                                     negative_wordcloud_base64=None,
                                     neutral_wordcloud_base64=None,
                                     highlighted_comments=None)

@app.route("/api/sentiments")
@login_required
def api_sentiments():
    return jsonify({
        "sentiment_percentages": sentiment_percentages,
        "detailed_sentiment_percentages": detailed_sentiment_percentages,
        "comments": comments_data
    })

if __name__ == "__main__":
    print("Starting Flask application...")
    app.run(debug=True)# app.py

import sys
import os
import pandas as pd
import numpy as np
import string
from textblob import TextBlob
from nltk.corpus import stopwords
import nltk
from wordcloud import WordCloud
import io
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend to avoid warning
import matplotlib.pyplot as plt
import base64
from datetime import datetime
import json
import time
import random
from collections import Counter
import re
from flask import Flask, jsonify, render_template_string, send_file, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
from functools import wraps
import tempfile
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors

# Check for potential naming conflicts
conflicting_files = ['enum.py', 'typing.py', 're.py', 'collections.py', 'datetime.py', 'json.py', 'os.py', 'sys.py']
for file in conflicting_files:
    if os.path.exists(file):
        print(f"ERROR: Found '{file}' in current directory. This conflicts with Python's standard library.")
        print(f"Please rename or remove '{file}' to avoid import issues.")
        sys.exit(1)

try:
    from flask import Flask, jsonify, render_template_string, send_file, request, redirect, url_for, flash, session
    from flask_sqlalchemy import SQLAlchemy
    from werkzeug.security import generate_password_hash, check_password_hash
    from functools import wraps
    import pandas as pd
    import string
    from textblob import TextBlob
    from nltk.corpus import stopwords
    import nltk
    from wordcloud import WordCloud
    import io
    import matplotlib
    matplotlib.use('Agg')  # Use non-interactive backend to avoid warning
    import matplotlib.pyplot as plt
    import base64
    from datetime import datetime
    import json
    import time
    import random
    from collections import Counter
    import re
except ImportError as e:
    print(f"Import error: {e}")
    print("Please ensure all required packages are installed.")
    sys.exit(1)
except Exception as e:
    print(f"Unexpected error during imports: {e}")
    sys.exit(1)

# Download stopwords if not already
try:
    nltk.data.find('corpora/stopwords')
except nltk.downloader.DownloadError:
    nltk.download('stopwords')

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Change this to a secure secret key
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///comments.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)

# User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# Comment model for user-submitted comments
class UserComment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    sentiment = db.Column(db.String(20))
    detailed_sentiment = db.Column(db.String(20))  # New field for detailed sentiment
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user = db.relationship('User', backref=db.backref('comments', lazy=True))

# Create tables
with app.app_context():
    try:
        db.create_all()
        
        # Create default admin user if not exists
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', is_admin=True)
            admin.set_password('admin123')  # Change this password in production
            db.session.add(admin)
            db.session.commit()
    except Exception as e:
        print(f"Database initialization error: {e}")
        sys.exit(1)

# Load dataset function - now loads from TaxTruth_Exploitation.csv
def load_dataset():
    """Load dataset from TaxTruth_Exploitation.csv"""
    try:
        print("Loading TaxTruth_Exploitation dataset from CSV...")
        df = pd.read_csv("TaxTruth_Exploitation.csv")
        print(f"Loaded {len(df)} records from TaxTruth_Exploitation dataset")
        
        # Check if required columns exist
        if 'PersonalComment' not in df.columns:
            print("Warning: 'PersonalComment' column not found in CSV")
            # Create a default comment column
            df['PersonalComment'] = "No comment provided"
        
        # Create a username column based on ID
        if 'Username' not in df.columns:
            print("Adding 'Username' column...")
            df['Username'] = [f"User{i+1}" for i in range(len(df))]
        
        # Create a date column if it doesn't exist
        if 'Date' not in df.columns:
            print("Adding 'Date' column...")
            df['Date'] = datetime.now().strftime("%Y-%m-%d")
        
        # Rename PersonalComment to Comment Text for consistency
        df = df.rename(columns={'PersonalComment': 'Comment Text'})
        
        return df
    except FileNotFoundError:
        print("TaxTruth_Exploitation.csv file not found. Creating sample dataset...")
        # Create sample data if file doesn't exist
        data = {
            "ID": [1, 2, 3, 4, 5],
            "PersonType": ["Poor", "MiddleClass", "Rich", "Billionaire", "Poor"],
            "Profession": ["Delivery Partner", "Nurse", "IT Engineer", "CEO", "Street Vendor"],
            "MonthlyIncome": [8701, 45227, 65454, 96818535, 14429],
            "TaxPaid": [871, 6633, 24370, 0, 871],
            "GSTItemsUsed": ["Petrol, Electricity", "Basic Groceries, Medical Supplies", "Cooking Gas, Basic Groceries", "Clothing, Fuel", "Electricity, Internet"],
            "GovernmentBenefit": ["Yes", "Yes", "No", "No", "Yes"],
            "BillionaireNearby": ["No", "No", "No", "Yes", "No"],
            "BillionaireTaxKnown": ["₹1000", "₹Unknown", "₹Unknown", "₹Unknown", "₹5000"],
            "FeelingExploited": ["Yes", "Yes", "No", "No", "Yes"],
            "PersonalComment": [
                "Why is everything taxed but not billionaires?",
                "Why is everything taxed but not billionaires?",
                "System is one-sided.",
                "System is one-sided.",
                "GST is killing my income."
            ],
            "Location": ["Jaipur, RJ", "Amritsar, PB", "Pune, MH", "Nagpur, MH", "Hyderabad, TS"]
        }
        df = pd.DataFrame(data)
        # Save the sample data to CSV file
        df.to_csv("TaxTruth_Exploitation.csv", index=False)
        print("Created sample TaxTruth dataset with 5 records")
        
        # Rename PersonalComment to Comment Text for consistency
        df = df.rename(columns={'PersonalComment': 'Comment Text'})
        
        # Create a username column based on ID
        df['Username'] = [f"User{i+1}" for i in range(len(df))]
        
        # Create a date column if it doesn't exist
        df['Date'] = datetime.now().strftime("%Y-%m-%d")
        
        return df
    except Exception as e:
        print(f"Error loading TaxTruth_Exploitation dataset: {e}")
        # Create empty dataframe as fallback
        return pd.DataFrame(columns=["Comment Text", "Date", "Username"])

# Text Preprocessing
stop_words = set(stopwords.words("english"))

def preprocess(text):
    if not isinstance(text, str):
        return ""
    text = text.lower()
    text = text.translate(str.maketrans("", "", string.punctuation))
    words = [w for w in text.split() if w not in stop_words]
    return " ".join(words)

# Sentiment analysis function
def get_sentiment(text):
    analysis = TextBlob(text)
    polarity = analysis.sentiment.polarity
    
    # Basic sentiment classification
    if polarity > 0:
        return "positive"
    elif polarity < 0:
        return "negative"
    else:
        return "neutral"

# Detailed sentiment analysis function
def get_detailed_sentiment(text):
    analysis = TextBlob(text)
    polarity = analysis.sentiment.polarity
    subjectivity = analysis.sentiment.subjectivity
    
    # More nuanced sentiment classification with adjusted thresholds
    if polarity > 0.3:
        return "strong-positive"  # Strongly positive
    elif polarity > 0:
        return "weak-positive"  # Weakly positive
    elif polarity > -0.3:
        return "weak-negative"  # Weakly negative
    else:
        return "strong-negative"  # Strongly negative

# Improved AI Summarizer function - now generates abstract summary and separate sentiment summaries
def generate_ai_summary(df):
    # Group by sentiment and ensure we have valid strings
    positive_comments = df[df['sentiment'] == 'positive']['Comment Text'].dropna().astype(str).tolist()
    negative_comments = df[df['sentiment'] == 'negative']['Comment Text'].dropna().astype(str).tolist()
    neutral_comments = df[df['sentiment'] == 'neutral']['Comment Text'].dropna().astype(str).tolist()
    
    # Group by detailed sentiment
    strong_positive_comments = df[df['detailed_sentiment'] == 'strong-positive']['Comment Text'].dropna().astype(str).tolist()
    weak_positive_comments = df[df['detailed_sentiment'] == 'weak-positive']['Comment Text'].dropna().astype(str).tolist()
    weak_negative_comments = df[df['detailed_sentiment'] == 'weak-negative']['Comment Text'].dropna().astype(str).tolist()
    strong_negative_comments = df[df['detailed_sentiment'] == 'strong-negative']['Comment Text'].dropna().astype(str).tolist()
    
    # Calculate counts and percentages
    total_comments = len(df)
    pos_count = len(positive_comments)
    neg_count = len(negative_comments)
    neu_count = len(neutral_comments)
    
    pos_pct = round((pos_count / total_comments) * 100, 1) if total_comments > 0 else 0
    neg_pct = round((neg_count / total_comments) * 100, 1) if total_comments > 0 else 0
    neu_pct = round((neu_count / total_comments) * 100, 1) if total_comments > 0 else 0
    
    # Detailed sentiment counts
    strong_positive_count = len(strong_positive_comments)
    weak_positive_count = len(weak_positive_comments)
    weak_negative_count = len(weak_negative_comments)
    strong_negative_count = len(strong_negative_comments)
    
    strong_positive_pct = round((strong_positive_count / total_comments) * 100, 1) if total_comments > 0 else 0
    weak_positive_pct = round((weak_positive_count / total_comments) * 100, 1) if total_comments > 0 else 0
    weak_negative_pct = round((weak_negative_count / total_comments) * 100, 1) if total_comments > 0 else 0
    strong_negative_pct = round((strong_negative_count / total_comments) * 100, 1) if total_comments > 0 else 0
    
    # Extract keywords for the entire dataset
    def extract_keywords(comments, n=10):
        if not comments:
            return []
        all_text = ' '.join(comments)
        words = preprocess(all_text).split()
        word_freq = Counter(words)
        return [word for word, count in word_freq.most_common(n)]
    
    all_keywords = extract_keywords(df['Comment Text'].tolist(), 10)
    
    # Analyze sentiment by PersonType
    sentiment_by_type = {}
    if 'PersonType' in df.columns:
        for ptype in df['PersonType'].unique():
            type_df = df[df['PersonType'] == ptype]
            type_total = len(type_df)
            if type_total > 0:
                type_pos = len(type_df[type_df['sentiment'] == 'positive'])
                type_neg = len(type_df[type_df['sentiment'] == 'negative'])
                type_neu = len(type_df[type_df['sentiment'] == 'neutral'])
                sentiment_by_type[ptype] = {
                    'positive': round((type_pos / type_total) * 100, 1),
                    'negative': round((type_neg / type_total) * 100, 1),
                    'neutral': round((type_neu / type_total) * 100, 1),
                    'count': type_total
                }
    
    # Analyze FeelingExploited distribution
    feeling_exploited_dist = {}
    if 'FeelingExploited' in df.columns:
        feeling_counts = df['FeelingExploited'].value_counts()
        for feeling in feeling_counts.index:
            feeling_exploited_dist[feeling] = {
                'count': feeling_counts[feeling],
                'percentage': round((feeling_counts[feeling] / total_comments) * 100, 1)
            }
    
    # Generate abstract summary
    abstract_parts = []
    
    # Overall sentiment
    if pos_pct > neg_pct and pos_pct > neu_pct:
        overall_sentiment = "predominantly positive"
    elif neg_pct > pos_pct and neg_pct > neu_pct:
        overall_sentiment = "predominantly negative"
    else:
        overall_sentiment = "mixed"
    
    abstract_parts.append(f"This analysis of {total_comments} comments reveals a {overall_sentiment} sentiment toward the tax system, with {pos_pct}% positive, {neg_pct}% negative, and {neu_pct}% neutral responses.")
    
    # Key themes
    if all_keywords:
        top_themes = ', '.join(all_keywords[:5])
        abstract_parts.append(f"Key themes emerging from the comments include {top_themes}.")
    
    # Sentiment by PersonType
    if sentiment_by_type:
        type_sentiments = []
        for ptype, data in sentiment_by_type.items():
            if data['negative'] > data['positive'] and data['negative'] > data['neutral']:
                type_sentiments.append(f"{ptype} respondents express predominantly negative sentiment ({data['negative']}%)")
            elif data['positive'] > data['negative'] and data['positive'] > data['neutral']:
                type_sentiments.append(f"{ptype} respondents express predominantly positive sentiment ({data['positive']}%)")
        
        if type_sentiments:
            abstract_parts.append(f"Notable patterns by economic status include: {', '.join(type_sentiments)}.")
    
    # FeelingExploited
    if feeling_exploited_dist:
        if 'Yes' in feeling_exploited_dist:
            exploited_pct = feeling_exploited_dist['Yes']['percentage']
            abstract_parts.append(f"Significantly, {exploited_pct}% of respondents report feeling exploited by the current tax system.")
    
    # Conclusion
    if neg_pct > 50:
        abstract_parts.append("The overall sentiment suggests widespread dissatisfaction with the tax system, particularly regarding fairness and equity.")
    elif pos_pct > 50:
        abstract_parts.append("The overall sentiment indicates general satisfaction with the tax system, though some concerns remain.")
    else:
        abstract_parts.append("The sentiment is divided, reflecting diverse perspectives on the tax system's effectiveness and fairness.")
    
    abstract_summary = ' '.join(abstract_parts)
    
    # Generate separate summaries for each sentiment
    # Positive summary
    positive_summary_parts = []
    if positive_comments:
        positive_keywords = extract_keywords(positive_comments, 5)
        positive_summary_parts.append(f"The positive sentiment analysis ({pos_pct}% of comments) reveals aspects of the tax system that respondents appreciate. Key themes include {', '.join(positive_keywords[:3])}.")
        
        # Analyze positive sentiment by PersonType
        positive_by_type = {}
        if 'PersonType' in df.columns:
            for ptype in df['PersonType'].unique():
                type_df = df[df['PersonType'] == ptype]
                type_positive = type_df[type_df['sentiment'] == 'positive']
                if len(type_positive) > 0:
                    positive_by_type[ptype] = len(type_positive)
            
            if positive_by_type:
                most_positive = max(positive_by_type, key=positive_by_type.get)
                positive_summary_parts.append(f"The {most_positive} group shows the highest number of positive comments.")
        
        positive_summary_parts.append("These positive comments suggest areas where the tax system is functioning well and meeting public expectations.")
    else:
        positive_summary_parts.append("No positive comments were found in the dataset.")
    
    positive_summary = ' '.join(positive_summary_parts)
    
    # Negative summary
    negative_summary_parts = []
    if negative_comments:
        negative_keywords = extract_keywords(negative_comments, 5)
        negative_summary_parts.append(f"The negative sentiment analysis ({neg_pct}% of comments) highlights significant concerns about the tax system. Key issues include {', '.join(negative_keywords[:3])}.")
        
        # Analyze negative sentiment by PersonType
        negative_by_type = {}
        if 'PersonType' in df.columns:
            for ptype in df['PersonType'].unique():
                type_df = df[df['PersonType'] == ptype]
                type_negative = type_df[type_df['sentiment'] == 'negative']
                if len(type_negative) > 0:
                    negative_by_type[ptype] = len(type_negative)
            
            if negative_by_type:
                most_negative = max(negative_by_type, key=negative_by_type.get)
                negative_summary_parts.append(f"The {most_negative} group expresses the most negative sentiment.")
        
        negative_summary_parts.append("These negative comments indicate areas where the tax system may need reform or improvement.")
    else:
        negative_summary_parts.append("No negative comments were found in the dataset.")
    
    negative_summary = ' '.join(negative_summary_parts)
    
    # Neutral summary
    neutral_summary_parts = []
    if neutral_comments:
        neutral_keywords = extract_keywords(neutral_comments, 5)
        neutral_summary_parts.append(f"The neutral sentiment analysis ({neu_pct}% of comments) provides factual observations about the tax system. Key topics include {', '.join(neutral_keywords[:3])}.")
        
        # Analyze neutral sentiment by PersonType
        neutral_by_type = {}
        if 'PersonType' in df.columns:
            for ptype in df['PersonType'].unique():
                type_df = df[df['PersonType'] == ptype]
                type_neutral = type_df[type_df['sentiment'] == 'neutral']
                if len(type_neutral) > 0:
                    neutral_by_type[ptype] = len(type_neutral)
            
            if neutral_by_type:
                most_neutral = max(neutral_by_type, key=neutral_by_type.get)
                neutral_summary_parts.append(f"The {most_neutral} group provides the most neutral comments.")
        
        neutral_summary_parts.append("These neutral comments offer balanced perspectives and objective assessments of the tax system.")
    else:
        neutral_summary_parts.append("No neutral comments were found in the dataset.")
    
    neutral_summary = ' '.join(neutral_summary_parts)
    
    return {
        "abstract": abstract_summary,
        "positive_summary": positive_summary,
        "negative_summary": negative_summary,
        "neutral_summary": neutral_summary,
        "statistics": {
            "total": total_comments,
            "positive": {
                "count": pos_count,
                "percentage": pos_pct
            },
            "negative": {
                "count": neg_count,
                "percentage": neg_pct
            },
            "neutral": {
                "count": neu_count,
                "percentage": neu_pct
            },
            "detailed": {
                "strong-positive": {
                    "count": strong_positive_count,
                    "percentage": strong_positive_pct
                },
                "weak-positive": {
                    "count": weak_positive_count,
                    "percentage": weak_positive_pct
                },
                "weak-negative": {
                    "count": weak_negative_count,
                    "percentage": weak_negative_pct
                },
                "strong-negative": {
                    "count": strong_negative_count,
                    "percentage": strong_negative_pct
                }
            },
            "sentiment_by_type": sentiment_by_type,
            "feeling_exploited": feeling_exploited_dist
        }
    }

def process_data(df):
    # Ensure all comments are strings and handle NaN values
    df['Comment Text'] = df['Comment Text'].fillna('').astype(str)
    
    print(f"Processing {len(df)} comments...")
    
    print("Preprocessing text...")
    df["cleaned_text"] = df["Comment Text"].apply(preprocess)
    
    # Sentiment Analysis
    print("Performing sentiment analysis...")
    try:
        df["sentiment"] = df["cleaned_text"].apply(get_sentiment)
        df["detailed_sentiment"] = df["cleaned_text"].apply(get_detailed_sentiment)
        print("Sentiment analysis completed.")
        
        # Print detailed sentiment distribution for debugging
        print("\nDetailed sentiment distribution:")
        print(df['detailed_sentiment'].value_counts())
        
    except Exception as e:
        print(f"Error during sentiment analysis: {e}")
        # Fallback: assign neutral sentiment to all
        df["sentiment"] = "neutral"
        df["detailed_sentiment"] = "weak-negative"
    
    # Print sample of processed data for debugging
    print("\nSample of processed data:")
    print(df[['Comment Text', 'sentiment', 'detailed_sentiment']].head(5))
    
    # Calculate sentiment counts and percentages
    sentiment_counts = df['sentiment'].value_counts().to_dict()
    total_comments = len(df)
    sentiment_percentages = {
        "positive": round((sentiment_counts.get("positive", 0) / total_comments) * 100, 2) if total_comments else 0,
        "negative": round((sentiment_counts.get("negative", 0) / total_comments) * 100, 2) if total_comments else 0,
        "neutral": round((sentiment_counts.get("neutral", 0) / total_comments) * 100, 2) if total_comments else 0,
    }
    
    # Calculate detailed sentiment counts and percentages
    detailed_sentiment_counts = df['detailed_sentiment'].value_counts().to_dict()
    detailed_sentiment_percentages = {
        "strong-positive": round((detailed_sentiment_counts.get("strong-positive", 0) / total_comments) * 100, 2) if total_comments else 0,
        "weak-positive": round((detailed_sentiment_counts.get("weak-positive", 0) / total_comments) * 100, 2) if total_comments else 0,
        "weak-negative": round((detailed_sentiment_counts.get("weak-negative", 0) / total_comments) * 100, 2) if total_comments else 0,
        "strong-negative": round((detailed_sentiment_counts.get("strong-negative", 0) / total_comments) * 100, 2) if total_comments else 0,
    }
    
    print(f"\nSentiment distribution: {sentiment_percentages}")
    print(f"Detailed sentiment distribution: {detailed_sentiment_percentages}")
    print(f"Total comments processed: {total_comments}")
    
    # Get sentiment by month
    if 'Date' in df.columns:
        # Try to parse dates with explicit format
        try:
            df['Date'] = pd.to_datetime(df['Date'], format='%Y-%m-%d')
        except:
            # If that fails, try to infer the format
            df['Date'] = pd.to_datetime(df['Date'], format='mixed')
        
        df['Month'] = df['Date'].dt.strftime('%b')
        monthly_sentiment = df.groupby(['Month', 'sentiment']).size().unstack(fill_value=0).to_dict()
    else:
        monthly_sentiment = {
            'positive': {'Jan': 65, 'Feb': 59, 'Mar': 70, 'Apr': 71, 'May': 66, 'Jun': 65, 'Jul': 72, 'Aug': 68, 'Sep': 64},
            'negative': {'Jan': 15, 'Feb': 19, 'Mar': 12, 'Apr': 13, 'May': 16, 'Jun': 15, 'Jul': 14, 'Aug': 19, 'Sep': 19},
            'neutral': {'Jan': 20, 'Feb': 22, 'Mar': 18, 'Apr': 16, 'May': 18, 'Jun': 20, 'Jul': 14, 'Aug': 13, 'Sep': 17}
        }
    
    # Get top keywords with frequencies
    all_words = ' '.join(df['cleaned_text']).split()
    word_freq = Counter(all_words)
    top_keywords = [word for word, count in word_freq.most_common(20)]
    
    # Get recent comments with proper sentiment distribution
    print("Selecting recent comments with sentiment distribution...")
    
    # Sort by date if available, otherwise by index
    if 'Date' in df.columns:
        # Try to parse dates with explicit format
        try:
            df['Date'] = pd.to_datetime(df['Date'], format='%Y-%m-%d')
        except:
            # If that fails, try to infer the format
            df['Date'] = pd.to_datetime(df['Date'], format='mixed')
        
        # Sort by date descending to get most recent first
        df_sorted = df.sort_values(by='Date', ascending=False)
    else:
        # If no date column, reverse the order to get most recent first (assuming original is chronological)
        df_sorted = df.iloc[::-1].reset_index(drop=True)

    # Check if 'Username' column exists before trying to access it
    if 'Username' not in df_sorted.columns:
        df_sorted['Username'] = [f"User{i+1}" for i in range(len(df_sorted))]

    # Take the top 5 most recent comments
    top_5 = df_sorted.head(5).copy()

    # Get the set of sentiments in the top_5
    sentiments_in_top5 = set(top_5['sentiment'].unique())
    all_sentiments = {'positive', 'negative', 'neutral'}
    missing_sentiments = all_sentiments - sentiments_in_top5

    # For each missing sentiment, get the most recent comment of that sentiment
    additional_comments = []
    for sentiment in missing_sentiments:
        # Get comments of this sentiment, sorted by date (descending)
        sentiment_comments = df_sorted[df_sorted['sentiment'] == sentiment]
        if not sentiment_comments.empty:
            # Take the first one (most recent)
            candidate = sentiment_comments.iloc[0]
            # Check if candidate is already in top_5 (by index)
            if candidate.name not in top_5.index:
                additional_comments.append(candidate)

    # Combine top_5 and additional_comments
    combined = pd.concat([top_5, pd.DataFrame(additional_comments)])

    # Sort combined by date (descending) if available, otherwise by the original order in combined
    if 'Date' in combined.columns:
        combined = combined.sort_values(by='Date', ascending=False)
    # else: we keep the order (top_5 first, then additional_comments)

    # Take the top 5
    recent_comments = combined.head(5)[["Comment Text", "sentiment", "detailed_sentiment", "Username"]].to_dict('records')
    
    # Check if 'Username' column exists before trying to access it
    if 'Username' in df.columns:
        comments_data = df[["Comment Text", "sentiment", "detailed_sentiment", "Username"]].to_dict(orient="records")
    else:
        # If 'Username' column doesn't exist, create it with default values
        df['Username'] = [f"User{i+1}" for i in range(len(df))]
        comments_data = df[["Comment Text", "sentiment", "detailed_sentiment", "Username"]].to_dict(orient="records")
    
    # Combine all cleaned text into one string
    all_text = " ".join(df["cleaned_text"].tolist())
    
    # Generate separate text for each sentiment for word clouds
    positive_text = " ".join(df[df['sentiment'] == 'positive']['cleaned_text'].tolist())
    negative_text = " ".join(df[df['sentiment'] == 'negative']['cleaned_text'].tolist())
    neutral_text = " ".join(df[df['sentiment'] == 'neutral']['cleaned_text'].tolist())
    
    # Generate AI summaries
    print("Generating AI summaries...")
    ai_summaries = generate_ai_summary(df)
    print("AI summaries generated.")
    
    # Calculate section sentiment data
    print("Calculating section sentiment data...")
    section_sentiment = calculate_section_sentiment(df)
    
    # Generate word clouds and store as base64 strings
    print("Generating word clouds...")
    all_wordcloud_base64 = generate_wordcloud_base64(all_text)
    positive_wordcloud_base64 = generate_wordcloud_base64(positive_text, color="#2ecc71")
    negative_wordcloud_base64 = generate_wordcloud_base64(negative_text, color="#e74c3c")
    neutral_wordcloud_base64 = generate_wordcloud_base64(neutral_text, color="#3498db")
    print("Word clouds generated.")
    
    # Process comments for highlighting important keywords
    print("Processing comments for keyword highlighting...")
    highlighted_comments = []
    for _, row in df.iterrows():
        comment_text = row['Comment Text']
        cleaned_text = row['cleaned_text']
        
        # Get important words from the cleaned text
        words = cleaned_text.split()
        important_words = [word for word in words if word in top_keywords[:10]]
        
        # Create a mapping of original words to their highlighted versions
        highlighted_mapping = {}
        for word in important_words:
            # Find the original word in the comment (case-insensitive)
            pattern = re.compile(r'\b' + re.escape(word) + r'\b', re.IGNORECASE)
            highlighted_mapping[word] = pattern
        
        # Apply highlighting to the comment text
        highlighted_comment = comment_text
        for word, pattern in highlighted_mapping.items():
            highlighted_comment = pattern.sub(f'<u>{word}</u>', highlighted_comment)
        
        highlighted_comments.append({
            'Comment Text': highlighted_comment,
            'sentiment': row['sentiment'],
            'detailed_sentiment': row['detailed_sentiment'],
            'Username': row['Username']
        })
    
    print("Comments processed for keyword highlighting.")
    
    return {
        "df": df,
        "sentiment_percentages": sentiment_percentages,
        "detailed_sentiment_percentages": detailed_sentiment_percentages,
        "total_comments": total_comments,
        "monthly_sentiment": monthly_sentiment,
        "top_keywords": top_keywords,
        "recent_comments": recent_comments,
        "comments_data": comments_data,
        "all_text": all_text,
        "positive_text": positive_text,
        "negative_text": negative_text,
        "neutral_text": neutral_text,
        "ai_summaries": ai_summaries,
        "section_sentiment": section_sentiment,
        "all_wordcloud_base64": all_wordcloud_base64,
        "positive_wordcloud_base64": positive_wordcloud_base64,
        "negative_wordcloud_base64": negative_wordcloud_base64,
        "neutral_wordcloud_base64": neutral_wordcloud_base64,
        "highlighted_comments": highlighted_comments
    }

def calculate_section_sentiment(df):
    # Define sections and keywords associated with each section
    sections = {
        "A1: Centralization": ["centralization", "central", "authority", "control", "power", "government", "initiative", "policy", "rule", "rules"],
        "A2: Compliance": ["compliance", "regulation", "rules", "adherence", "requirements", "follow", "obey", "law", "regulations"],
        "A3: Transparency": ["transparency", "open", "clear", "disclosure", "visibility", "transparent", "clarity", "understand"],
        "B1: Implementation": ["implementation", "execution", "enforcement", "apply", "deploy", "carry", "put", "effect", "implementing"],
        "B2: Regulation": ["regulation", "regulate", "rules", "standards", "guidelines", "law", "policy", "regulating"],
        "B3: Accountability": ["accountability", "responsible", "answerable", "liability", "oversight", "responsibility", "answer"],
        "C1: Data Rights": ["rights", "privacy", "consent", "ownership", "access", "data", "protection", "right"],
        "C2: Security": ["security", "protection", "safe", "secure", "breach", "safety", "protect"],
        "C3: Enforcement": ["enforcement", "penalty", "punishment", "fine", "sanction", "impose", "enforce", "enforcing"],
        "D1: Oversight": ["oversight", "monitor", "supervise", "watch", "inspect", "supervision", "monitoring"],
        "D2: User Control": ["control", "user", "choice", "option", "preference", "user control", "choices"],
        "D3: Breach Notification": ["breach", "notification", "alert", "inform", "report", "notify", "notifying"]
    }
    
    section_data = {}
    
    # Debug: Print first few comments to see what words we're working with
    print("Sample comments for keyword matching:")
    for i, comment in enumerate(df['cleaned_text'].head(5)):
        print(f"{i+1}: {comment}")
    
    for section, keywords in sections.items():
        print(f"\nProcessing section: {section}")
        print(f"Keywords: {keywords}")
        
        # Find comments that mention keywords for this section
        # Create a regex pattern that matches whole words only
        pattern = r'\b(' + '|'.join(keywords) + r')\b'
        section_comments = df[df['cleaned_text'].str.contains(pattern, case=False, na=False, regex=True)]
        
        print(f"Found {len(section_comments)} matching comments")
        
        if len(section_comments) > 0:
            # Calculate sentiment distribution for this section
            section_sentiment_counts = section_comments['sentiment'].value_counts().to_dict()
            section_total = len(section_comments)
            
            # Calculate detailed sentiment distribution
            section_detailed_sentiment_counts = section_comments['detailed_sentiment'].value_counts().to_dict()
            
            section_data[section] = {
                "positive": round((section_sentiment_counts.get("positive", 0) / section_total) * 100, 1) if section_total else 0,
                "negative": round((section_sentiment_counts.get("negative", 0) / section_total) * 100, 1) if section_total else 0,
                "neutral": round((section_sentiment_counts.get("neutral", 0) / section_total) * 100, 1) if section_total else 0,
                "detailed": {
                    "strong-positive": round((section_detailed_sentiment_counts.get("strong-positive", 0) / section_total) * 100, 1) if section_total else 0,
                    "weak-positive": round((section_detailed_sentiment_counts.get("weak-positive", 0) / section_total) * 100, 1) if section_total else 0,
                    "weak-negative": round((section_detailed_sentiment_counts.get("weak-negative", 0) / section_total) * 100, 1) if section_total else 0,
                    "strong-negative": round((section_detailed_sentiment_counts.get("strong-negative", 0) / section_total) * 100, 1) if section_total else 0,
                },
                "total": section_total,
                "comments": section_comments[["Comment Text", "sentiment", "detailed_sentiment", "Username"]].head(3).to_dict('records')
            }
            
            print(f"Sentiment distribution: {section_data[section]}")
        else:
            # If no comments match, provide default values
            section_data[section] = {
                "positive": 25.0,
                "negative": 25.0,
                "neutral": 25.0,
                "detailed": {
                    "strong-positive": 12.5,
                    "weak-positive": 12.5,
                    "weak-negative": 12.5,
                    "strong-negative": 12.5,
                },
                "total": 0,
                "comments": []
            }
            print("No comments matched, using default values")
    
    return section_data

# Initialize global variables to None
df = None
sentiment_percentages = None
detailed_sentiment_percentages = None
total_comments = None
monthly_sentiment = None
top_keywords = None
recent_comments = None
comments_data = None
all_text = None
positive_text = None
negative_text = None
neutral_text = None
ai_summaries = None
section_sentiment = None
all_wordcloud_base64 = None
positive_wordcloud_base64 = None
negative_wordcloud_base64 = None
neutral_wordcloud_base64 = None
highlighted_comments = None

# Function to load and process data from TaxTruth_Exploitation.csv
def load_and_process_data():
    global df, sentiment_percentages, detailed_sentiment_percentages, total_comments, monthly_sentiment, top_keywords, recent_comments, comments_data, all_text, positive_text, negative_text, neutral_text, ai_summaries, section_sentiment, all_wordcloud_base64, positive_wordcloud_base64, negative_wordcloud_base64, neutral_wordcloud_base64, highlighted_comments

    print("Loading and processing TaxTruth_Exploitation dataset...")
    df = load_dataset()
    
    # If df is empty, create a sample dataframe
    if df.empty:
        print("No data fetched, creating sample data")
        data = [
            {"Comment Text": "This is a great initiative by the government", "Date": "2023-01-15", "Username": "@gov_supporter"},
            {"Comment Text": "I'm not happy with the current regulations", "Date": "2023-02-20", "Username": "@concerned_citizen"},
            {"Comment Text": "The new policy seems reasonable", "Date": "2023-03-10", "Username": "@policy_analyst"},
            {"Comment Text": "This will negatively impact small businesses", "Date": "2023-04-05", "Username": "@business_owner"},
            {"Comment Text": "Looking forward to the implementation", "Date": "2023-05-12", "Username": "@optimist_view"}
        ]
        df = pd.DataFrame(data)
    
    processed_data = process_data(df)
    df = processed_data["df"]
    sentiment_percentages = processed_data["sentiment_percentages"]
    detailed_sentiment_percentages = processed_data["detailed_sentiment_percentages"]
    total_comments = processed_data["total_comments"]
    monthly_sentiment = processed_data["monthly_sentiment"]
    top_keywords = processed_data["top_keywords"]
    recent_comments = processed_data["recent_comments"]
    comments_data = processed_data["comments_data"]
    all_text = processed_data["all_text"]
    positive_text = processed_data["positive_text"]
    negative_text = processed_data["negative_text"]
    neutral_text = processed_data["neutral_text"]
    ai_summaries = processed_data["ai_summaries"]
    section_sentiment = processed_data["section_sentiment"]
    all_wordcloud_base64 = processed_data["all_wordcloud_base64"]
    positive_wordcloud_base64 = processed_data["positive_wordcloud_base64"]
    negative_wordcloud_base64 = processed_data["negative_wordcloud_base64"]
    neutral_wordcloud_base64 = processed_data["neutral_wordcloud_base64"]
    highlighted_comments = processed_data["highlighted_comments"]
    print("Data loading and processing completed.")

# Function to reprocess data from CSV file
def reprocess_data():
    global df, sentiment_percentages, detailed_sentiment_percentages, total_comments, monthly_sentiment, top_keywords, recent_comments, comments_data, all_text, positive_text, negative_text, neutral_text, ai_summaries, section_sentiment, all_wordcloud_base64, positive_wordcloud_base64, negative_wordcloud_base64, neutral_wordcloud_base64, highlighted_comments

    print("Reprocessing data from TaxTruth_Exploitation.csv file...")
    try:
        df = pd.read_csv("TaxTruth_Exploitation.csv")
        print(f"Loaded {len(df)} records from TaxTruth_Exploitation.csv file")
        
        # Rename PersonalComment to Comment Text for consistency
        df = df.rename(columns={'PersonalComment': 'Comment Text'})
        
        # Ensure required columns exist
        if 'Username' not in df.columns:
            print("Adding missing 'Username' column...")
            df['Username'] = [f"User{i+1}" for i in range(len(df))]
        
        if 'Date' not in df.columns:
            print("Adding missing 'Date' column...")
            df['Date'] = datetime.now().strftime("%Y-%m-%d")
        
        # Save updated dataframe back to CSV file
        df.to_csv("TaxTruth_Exploitation.csv", index=False)
        print("Updated CSV file with required columns")
    except Exception as e:
        print(f"Error loading TaxTruth_Exploitation dataset: {e}")
        flash(f'Error loading dataset: {str(e)}', 'danger')
        df = pd.DataFrame()
    
    # If df is empty, reset all variables and return
    if df.empty:
        print("No data available in the uploaded dataset.")
        sentiment_percentages = None
        detailed_sentiment_percentages = None
        total_comments = None
        monthly_sentiment = None
        top_keywords = None
        recent_comments = None
        comments_data = None
        all_text = None
        positive_text = None
        negative_text = None
        neutral_text = None
        ai_summaries = None
        section_sentiment = None
        all_wordcloud_base64 = None
        positive_wordcloud_base64 = None
        negative_wordcloud_base64 = None
        neutral_wordcloud_base64 = None
        highlighted_comments = None
        return
    
    # Process the data
    processed_data = process_data(df)
    df = processed_data["df"]
    sentiment_percentages = processed_data["sentiment_percentages"]
    detailed_sentiment_percentages = processed_data["detailed_sentiment_percentages"]
    total_comments = processed_data["total_comments"]
    monthly_sentiment = processed_data["monthly_sentiment"]
    top_keywords = processed_data["top_keywords"]
    recent_comments = processed_data["recent_comments"]
    comments_data = processed_data["comments_data"]
    all_text = processed_data["all_text"]
    positive_text = processed_data["positive_text"]
    negative_text = processed_data["negative_text"]
    neutral_text = processed_data["neutral_text"]
    ai_summaries = processed_data["ai_summaries"]
    section_sentiment = processed_data["section_sentiment"]
    all_wordcloud_base64 = processed_data["all_wordcloud_base64"]
    positive_wordcloud_base64 = processed_data["positive_wordcloud_base64"]
    negative_wordcloud_base64 = processed_data["negative_wordcloud_base64"]
    neutral_wordcloud_base64 = processed_data["neutral_wordcloud_base64"]
    highlighted_comments = processed_data["highlighted_comments"]
    print("Data reprocessing completed.")

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# Word Cloud Generation - Optimized to return base64 string
def generate_wordcloud_base64(text, color=None):
    if not text or len(text.strip()) == 0:
        # Create a simple image with "No data available" text
        img_buffer = io.BytesIO()
        plt.figure(figsize=(6,4), dpi=100)
        plt.text(0.5, 0.5, 'No data available', 
                 horizontalalignment='center', verticalalignment='center', 
                 transform=plt.gca().transAxes, fontsize=16)
        plt.axis('off')
        plt.tight_layout(pad=0)
        plt.savefig(img_buffer, format="png")
        plt.close()
        img_buffer.seek(0)
        return base64.b64encode(img_buffer.read()).decode('utf-8')
    
    # Set contour color based on sentiment
    contour_color = color if color else 'steelblue'
    
    # Create word cloud with optimized settings
    wc = WordCloud(
        background_color="white",
        max_words=100,  # Reduced for faster generation
        width=600,
        height=400,
        contour_width=3,
        contour_color=contour_color,
        collocations=False,  # Disable collocations for faster generation
        random_state=42  # For reproducibility
    ).generate(text)
    
    # Save to a bytes buffer
    img_buffer = io.BytesIO()
    plt.figure(figsize=(6,4), dpi=100)
    plt.imshow(wc, interpolation="bilinear")
    plt.axis("off")
    plt.tight_layout(pad=0)
    plt.savefig(img_buffer, format="png")
    plt.close()
    img_buffer.seek(0)
    
    # Return as base64 string
    return base64.b64encode(img_buffer.read()).decode('utf-8')

# Word Cloud Routes - Now serve base64 encoded images
@app.route("/wordcloud.png")
@login_required
def wordcloud_png():
    if all_wordcloud_base64:
        img_data = base64.b64decode(all_wordcloud_base64)
        return send_file(io.BytesIO(img_data), mimetype="image/png")
    else:
        # Fallback to generating on the fly
        img = generate_wordcloud_image(all_text)
        return send_file(img, mimetype="image/png")

@app.route("/positive_wordcloud.png")
@login_required
def positive_wordcloud_png():
    if positive_wordcloud_base64:
        img_data = base64.b64decode(positive_wordcloud_base64)
        return send_file(io.BytesIO(img_data), mimetype="image/png")
    else:
        # Fallback to generating on the fly
        img = generate_positive_wordcloud_image(positive_text)
        return send_file(img, mimetype="image/png")

@app.route("/negative_wordcloud.png")
@login_required
def negative_wordcloud_png():
    if negative_wordcloud_base64:
        img_data = base64.b64decode(negative_wordcloud_base64)
        return send_file(io.BytesIO(img_data), mimetype="image/png")
    else:
        # Fallback to generating on the fly
        img = generate_negative_wordcloud_image(negative_text)
        return send_file(img, mimetype="image/png")

@app.route("/neutral_wordcloud.png")
@login_required
def neutral_wordcloud_png():
    if neutral_wordcloud_base64:
        img_data = base64.b64decode(neutral_wordcloud_base64)
        return send_file(io.BytesIO(img_data), mimetype="image/png")
    else:
        # Fallback to generating on the fly
        img = generate_neutral_wordcloud_image(neutral_text)
        return send_file(img, mimetype="image/png")

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['is_admin'] = user.is_admin
            
            # For admin users, redirect to upload page if no data is available
            if user.is_admin:
                if df is None or sentiment_percentages is None:
                    flash('Please upload a dataset to access the dashboard', 'info')
                    return redirect(url_for('upload_dataset_page'))
                else:
                    return redirect(url_for('index'))
            else:
                return redirect(url_for('index'))
        else:
            flash('Invalid username or password', 'danger')
    
    return render_template_string(login_template)

# Logout route
@app.route('/logout')
def logout():
    # Clear global data variables
    global df, sentiment_percentages, detailed_sentiment_percentages, total_comments, monthly_sentiment, top_keywords, recent_comments, comments_data, all_text, positive_text, negative_text, neutral_text, ai_summaries, section_sentiment, all_wordcloud_base64, positive_wordcloud_base64, negative_wordcloud_base64, neutral_wordcloud_base64, highlighted_comments
    
    df = None
    sentiment_percentages = None
    detailed_sentiment_percentages = None
    total_comments = None
    monthly_sentiment = None
    top_keywords = None
    recent_comments = None
    comments_data = None
    all_text = None
    positive_text = None
    negative_text = None
    neutral_text = None
    ai_summaries = None
    section_sentiment = None
    all_wordcloud_base64 = None
    positive_wordcloud_base64 = None
    negative_wordcloud_base64 = None
    neutral_wordcloud_base64 = None
    highlighted_comments = None
    
    # Clear session
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

# Register route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return redirect(url_for('register'))
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'danger')
            return redirect(url_for('register'))
        
        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    
    return render_template_string(register_template)

# Comment submission route
@app.route('/submit_comment', methods=['POST'])
@login_required
def submit_comment():
    global df, sentiment_percentages, detailed_sentiment_percentages, total_comments, monthly_sentiment, top_keywords, recent_comments, comments_data, all_text, positive_text, negative_text, neutral_text, ai_summaries, section_sentiment, all_wordcloud_base64, positive_wordcloud_base64, negative_wordcloud_base64, neutral_wordcloud_base64, highlighted_comments
    
    comment_text = request.form.get('comment')
    if comment_text:
        # Analyze sentiment
        cleaned_text = preprocess(comment_text)
        sentiment = get_sentiment(cleaned_text)
        detailed_sentiment = get_detailed_sentiment(cleaned_text)
        
        # Save to database
        new_comment = UserComment(
            text=comment_text,
            sentiment=sentiment,
            detailed_sentiment=detailed_sentiment,
            user_id=session['user_id']
        )
        db.session.add(new_comment)
        db.session.commit()
        
        # Add to CSV file
        new_row = {
            "ID": len(df) + 1 if df is not None else 1,
            "PersonType": "User",
            "Profession": "General",
            "MonthlyIncome": 0,
            "TaxPaid": 0,
            "GSTItemsUsed": "",
            "GovernmentBenefit": "No",
            "BillionaireNearby": "No",
            "BillionaireTaxKnown": "₹0",
            "FeelingExploited": "Maybe",
            "PersonalComment": comment_text,
            "Location": "Online",
            "Username": session['username'],
            "Date": datetime.now().strftime("%Y-%m-%d")
        }
        
        # Load existing data
        try:
            existing_df = pd.read_csv("TaxTruth_Exploitation.csv")
        except:
            existing_df = pd.DataFrame()
        
        # Append new comment
        if not existing_df.empty:
            updated_df = pd.concat([existing_df, pd.DataFrame([new_row])], ignore_index=True)
        else:
            updated_df = pd.DataFrame([new_row])
        
        # Save back to CSV file
        updated_df.to_csv("TaxTruth_Exploitation.csv", index=False)
        
        # Reprocess data from CSV file
        reprocess_data()
        
        flash('Comment submitted successfully!', 'success')
    else:
        flash('Comment cannot be empty', 'danger')
    
    return redirect(url_for('index'))

# Debug route
@app.route("/debug")
@login_required
def debug_data():
    if not session.get('is_admin'):
        return "Access denied", 403
        
    debug_info = {
        "dataset_comments": len(df) if df is not None else 0,
        "db_comments": UserComment.query.count(),
        "total_comments_global": total_comments,
        "dataset_file_exists": os.path.exists("TaxTruth_Exploitation.csv"),
        "dataset_file_size": os.path.getsize("TaxTruth_Exploitation.csv") if os.path.exists("TaxTruth_Exploitation.csv") else 0,
        "detailed_sentiment_percentages": detailed_sentiment_percentages
    }
    
    # Try to load and verify dataset
    try:
        data = pd.read_csv("TaxTruth_Exploitation.csv")
        debug_info["dataset_file_records"] = len(data)
        
        # Check for required columns
        if not data.empty:
            sample = data.iloc[0]
            debug_info["has_comment_text"] = "Comment Text" in sample or "PersonalComment" in sample
            debug_info["has_username"] = "Username" in sample
    except Exception as e:
        debug_info["dataset_error"] = str(e)
    
    return jsonify(debug_info)

# Error handler for large files
@app.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(e):
    flash('File too large. Maximum size is 16MB.', 'danger')
    return redirect(url_for('index'))

# Function to process uploaded files
def process_uploaded_file(file_path):
    """Process uploaded dataset file in various formats"""
    file_ext = os.path.splitext(file_path)[1].lower()
    
    try:
        if file_ext == '.csv':
            df = pd.read_csv(file_path)
        elif file_ext in ['.xls', '.xlsx']:
            df = pd.read_excel(file_path)
        elif file_ext == '.json':
            df = pd.read_json(file_path)
        elif file_ext == '.tsv':
            df = pd.read_csv(file_path, sep='\t')
        else:
            raise ValueError("Unsupported file format. Please upload CSV, Excel, JSON, or TSV files.")
        
        # Check if we have a comment column
        comment_col = None
        possible_columns = ['Comment Text', 'PersonalComment', 'comment', 'text', 'comments', 'feedback', 'review']
        
        for col in possible_columns:
            if col in df.columns:
                comment_col = col
                break
        
        if comment_col is None:
            # Try to find a column that has text data
            for col in df.columns:
                if df[col].dtype == 'object':
                    # Check if it contains text (not numbers or dates)
                    sample = df[col].dropna().head(5)
                    if all(isinstance(x, str) for x in sample):
                        comment_col = col
                        break
        
        if comment_col is None:
            raise ValueError("No comment column found in the dataset. Please ensure your file has a column with text comments.")
        
        # Rename the comment column to 'Comment Text' for consistency
        df = df.rename(columns={comment_col: 'Comment Text'})
        
        # Ensure we have a 'Username' column
        if 'Username' not in df.columns:
            df['Username'] = [f"User{i+1}" for i in range(len(df))]
        
        # Ensure we have a 'Date' column
        if 'Date' not in df.columns:
            df['Date'] = datetime.now().strftime("%Y-%m-%d")
        
        return df
    except Exception as e:
        raise ValueError(f"Error processing file: {str(e)}")

# Route for uploading datasets
@app.route('/upload_dataset', methods=['POST'])
@login_required
def upload_dataset():
    if not session.get('is_admin'):
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    if 'dataset_file' not in request.files:
        flash('No file selected', 'danger')
        return redirect(url_for('upload_dataset_page'))
    
    file = request.files['dataset_file']
    if file.filename == '':
        flash('No file selected', 'danger')
        return redirect(url_for('upload_dataset_page'))
    
    if file:
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        try:
            # Process the uploaded file
            df_uploaded = process_uploaded_file(file_path)
            
            # Save the uploaded data to the main CSV file
            df_uploaded.to_csv("TaxTruth_Exploitation.csv", index=False)
            
            # Reprocess the data
            reprocess_data()
            
            flash('Dataset uploaded and processed successfully!', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            flash(f'Error processing dataset: {str(e)}', 'danger')
            return redirect(url_for('upload_dataset_page'))
    
    return redirect(url_for('upload_dataset_page'))

# Route for dataset preview
@app.route('/preview_dataset', methods=['POST'])
@login_required
def preview_dataset():
    if not session.get('is_admin'):
        return jsonify({"error": "Access denied"}), 403
    
    if 'dataset_file' not in request.files:
        return jsonify({"error": "No file selected"}), 400
    
    file = request.files['dataset_file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    
    try:
        # Save the file temporarily
        filename = secure_filename(file.filename)
        file_path = os.path.join(tempfile.gettempdir(), filename)
        file.save(file_path)
        
        # Process the uploaded file
        df_uploaded = process_uploaded_file(file_path)
        
        # Clean up temporary file
        os.remove(file_path)
        
        # Return preview data
        preview_data = {
            "columns": df_uploaded.columns.tolist(),
            "rows": df_uploaded.head(5).to_dict('records'),
            "total_rows": len(df_uploaded)
        }
        
        return jsonify(preview_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# New route for upload dataset page (GET)
@app.route('/upload_dataset_page')
@login_required
def upload_dataset_page():
    if not session.get('is_admin'):
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    # If data already exists, show dashboard
    if df is not None and sentiment_percentages is not None:
        return redirect(url_for('index'))
    
    return render_template_string(upload_prompt_template)

# Route for generating and downloading PDF report
@app.route('/generate_report')
@login_required
def generate_report():
    if not session.get('is_admin'):
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    if df is None or sentiment_percentages is None:
        flash('No data available for report generation', 'danger')
        return redirect(url_for('index'))
    
    # Create a PDF document
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    
    # Get styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        textColor=colors.darkblue
    )
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=12,
        textColor=colors.darkblue
    )
    
    # Add title
    elements.append(Paragraph("Sentiment Analysis Report", title_style))
    elements.append(Spacer(1, 12))
    
    # Add generation date
    elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
    elements.append(Spacer(1, 12))
    
    # Add summary statistics
    elements.append(Paragraph("Summary Statistics", heading_style))
    elements.append(Spacer(1, 6))
    
    stats_data = [
        ['Metric', 'Value'],
        ['Total Comments', str(total_comments)],
        ['Positive Sentiment', f"{sentiment_percentages['positive']}%"],
        ['Negative Sentiment', f"{sentiment_percentages['negative']}%"],
        ['Neutral Sentiment', f"{sentiment_percentages['neutral']}%"]
    ]
    
    stats_table = Table(stats_data, colWidths=[2*inch, 1.5*inch])
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(stats_table)
    elements.append(Spacer(1, 20))
    
    # Add detailed sentiment analysis
    elements.append(Paragraph("Detailed Sentiment Analysis", heading_style))
    elements.append(Spacer(1, 6))
    
    detailed_stats_data = [
        ['Sentiment Type', 'Percentage'],
        ['Strong Positive', f"{detailed_sentiment_percentages['strong-positive']}%"],
        ['Weak Positive', f"{detailed_sentiment_percentages['weak-positive']}%"],
        ['Weak Negative', f"{detailed_sentiment_percentages['weak-negative']}%"],
        ['Strong Negative', f"{detailed_sentiment_percentages['strong-negative']}%"]
    ]
    
    detailed_table = Table(detailed_stats_data, colWidths=[2*inch, 1.5*inch])
    detailed_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(detailed_table)
    elements.append(Spacer(1, 20))
    
    # Add abstract summary
    elements.append(Paragraph("Abstract Summary", heading_style))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph(ai_summaries['abstract'], styles['Normal']))
    elements.append(Spacer(1, 20))
    
    # Add sentiment summaries
    elements.append(Paragraph("Positive Sentiment Summary", heading_style))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph(ai_summaries['positive_summary'], styles['Normal']))
    elements.append(Spacer(1, 20))
    
    elements.append(Paragraph("Negative Sentiment Summary", heading_style))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph(ai_summaries['negative_summary'], styles['Normal']))
    elements.append(Spacer(1, 20))
    
    elements.append(Paragraph("Neutral Sentiment Summary", heading_style))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph(ai_summaries['neutral_summary'], styles['Normal']))
    elements.append(Spacer(1, 20))
    
    # Add top keywords
    elements.append(Paragraph("Top Keywords", heading_style))
    elements.append(Spacer(1, 6))
    
    keywords_text = ", ".join(top_keywords[:10])
    elements.append(Paragraph(keywords_text, styles['Normal']))
    elements.append(Spacer(1, 20))
    
    # Add word cloud images if available
    if all_wordcloud_base64:
        elements.append(Paragraph("Word Cloud - All Comments", heading_style))
        elements.append(Spacer(1, 6))
        
        # Decode base64 image and save to temporary file
        wordcloud_img = io.BytesIO(base64.b64decode(all_wordcloud_base64))
        elements.append(Image(wordcloud_img, width=5*inch, height=3.33*inch))
        elements.append(Spacer(1, 20))
    
    # Build PDF
    doc.build(elements)
    
    # Move to beginning of buffer
    buffer.seek(0)
    
    # Return PDF file
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"sentiment_analysis_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
        mimetype='application/pdf'
    )

# Upload prompt template
upload_prompt_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Upload Dataset - Sentiment Analysis</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f5f7fb;
            color: #333;
        }
        .upload-container {
            max-width: 800px;
            margin: 50px auto;
            padding: 30px;
            background-color: white;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        .header {
            background: linear-gradient(120deg, #4361ee, #3f37c9);
            color: white;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 30px;
            text-align: center;
        }
        .upload-area {
            border: 2px dashed #4361ee;
            border-radius: 10px;
            padding: 40px;
            text-align: center;
            margin-bottom: 20px;
            background-color: #f8f9ff;
        }
        .btn-primary {
            background-color: #4361ee;
            border-color: #4361ee;
        }
        .file-info {
            margin-top: 20px;
            font-size: 14px;
            color: #6c757d;
        }
    </style>
</head>
<body>
    <div class="upload-container">
        <div class="header">
            <h1><i class="fas fa-upload me-2"></i>Upload Dataset for Analysis</h1>
            <p class="mb-0">Please upload a dataset to begin sentiment analysis</p>
        </div>
        
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
                        {{ message }}
                        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        
        <div class="upload-area">
            <i class="fas fa-cloud-upload-alt fa-3x text-primary mb-3"></i>
            <h4>Upload Your Dataset</h4>
            <p class="text-muted">Supported formats: CSV, Excel, JSON, TSV (Max 16MB)</p>
            
            <form method="POST" action="{{ url_for('upload_dataset') }}" enctype="multipart/form-data">
                <div class="mb-3">
                    <input type="file" class="form-control" id="dataset_file" name="dataset_file" accept=".csv,.xls,.xlsx,.json,.tsv" required>
                </div>
                <button type="submit" class="btn btn-primary">
                    <i class="fas fa-upload me-2"></i>Upload and Process
                </button>
            </form>
            
            <div class="file-info">
                <p><strong>Note:</strong> The dataset should contain a column with text comments for sentiment analysis.</p>
                <p>After uploading, the system will analyze the sentiment of the comments and generate insights.</p>
            </div>
        </div>
        
        <div class="text-center mt-4">
            <a href="{{ url_for('logout') }}" class="btn btn-outline-secondary">
                <i class="fas fa-sign-out-alt me-1"></i> Logout
            </a>
        </div>
    </div>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

# Main HTML Template with Enhanced Dashboard
html_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sentiment Analysis Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root {
            --primary: #4361ee;
            --secondary: #3f37c9;
            --accent: #4895ef;
            --light: #f8f9fa;
            --dark: #212529;
            --success: #4cc9f0;
            --danger: #f72585;
            --warning: #ff9e00;
            --gray: #6c757d;
            --strong-positive: #2ecc71;
            --weak-positive: #3498db;
            --weak-negative: #f39c12;
            --strong-negative: #e74c3c;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f5f7fb;
            color: #333;
        }
        
        .dashboard-container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }
        
        .header {
            background: linear-gradient(120deg, var(--primary), var(--secondary));
            color: white;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        
        .card {
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
            margin-bottom: 20px;
            border: none;
            transition: transform 0.2s;
        }
        
        .card:hover {
            transform: translateY(-5px);
            box-shadow: 0 8px 15px rgba(0, 0, 0, 0.1);
        }
        
        .card-header {
            background-color: white;
            border-bottom: 1px solid #eaeaea;
            font-weight: 600;
            padding: 15px 20px;
            border-radius: 10px 10px 0 0 !important;
        }
        
        .metric-card {
            text-align: center;
            padding: 15px;
        }
        
        .metric-value {
            font-size: 24px;
            font-weight: 700;
            color: var(--primary);
        }
        
        .metric-label {
            font-size: 14px;
            color: var(--gray);
        }
        
        .positive {
            color: var(--success);
        }
        
        .negative {
            color: var(--danger);
        }
        
        .neutral {
            color: var(--gray);
        }
        
        .strong-positive {
            color: var(--strong-positive);
        }
        
        .weak-positive {
            color: var(--weak-positive);
        }
        
        .weak-negative {
            color: var(--weak-negative);
        }
        
        .strong-negative {
            color: var(--strong-negative);
        }
        
        .nav-pills .nav-link.active {
            background-color: var(--primary);
        }
        
        .btn-primary {
            background-color: var(--primary);
            border-color: var(--primary);
        }
        
        .section-title {
            border-left: 4px solid var(--primary);
            padding-left: 10px;
            margin: 20px 0 15px;
        }
        
        .search-box {
            border-radius: 20px;
            padding: 8px 20px;
            border: 1px solid #eaeaea;
        }
        
        .heat-map {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
            gap: 10px;
            margin-top: 15px;
        }
        
        .heat-item {
            padding: 10px;
            border-radius: 8px;
            text-align: center;
            background-color: #e9ecef;
            cursor: pointer;
            transition: all 0.3s;
        }
        
        .heat-item:hover {
            background-color: var(--accent);
            color: white;
        }
        
        .heat-positive {
            background-color: rgba(76, 201, 240, 0.2);
        }
        
        .heat-negative {
            background-color: rgba(247, 37, 133, 0.2);
        }
        
        .interactive-panel {
            background-color: #f8f9fa;
            border-radius: 10px;
            padding: 20px;
            margin-top: 20px;
        }
        
        .filter-options {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            margin-bottom: 15px;
        }
        
        .filter-btn {
            background-color: white;
            border: 1px solid #eaeaea;
            border-radius: 20px;
            padding: 5px 15px;
            font-size: 14px;
            cursor: pointer;
        }
        
        .filter-btn.active {
            background-color: var(--primary);
            color: white;
            border-color: var(--primary);
        }
        
        .footer {
            background: linear-gradient(120deg, var(--secondary), var(--primary));
            color: white;
            padding: 20px;
            border-radius: 10px;
            margin-top: 30px;
        }
        
        .user-avatar {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            color: white;
        }
        
        .bg-primary { background-color: var(--primary); }
        .bg-success { background-color: var(--success); }
        .bg-warning { background-color: var(--warning); }
        
        .comment-text {
            font-size: 14px;
            line-height: 1.5;
        }
        
        .sentiment-badge {
            font-size: 12px;
            padding: 3px 8px;
            border-radius: 12px;
        }
        
        .badge-positive {
            background-color: rgba(76, 201, 240, 0.2);
            color: var(--success);
        }
        
        .badge-negative {
            background-color: rgba(247, 37, 133, 0.2);
            color: var(--danger);
        }
        
        .badge-neutral {
            background-color: rgba(108, 117, 125, 0.2);
            color: var(--gray);
        }
        
        .badge-strong-positive {
            background-color: rgba(46, 204, 113, 0.2);
            color: var(--strong-positive);
        }
        
        .badge-weak-positive {
            background-color: rgba(52, 152, 219, 0.2);
            color: var(--weak-positive);
        }
        
        .badge-weak-negative {
            background-color: rgba(243, 156, 18, 0.2);
            color: var(--weak-negative);
        }
        
        .badge-strong-negative {
            background-color: rgba(231, 76, 60, 0.2);
            color: var(--strong-negative);
        }
        
        .comment-form {
            background-color: #f8f9fa;
            border-radius: 10px;
            padding: 20px;
            margin: 20px 0;
        }
        
        .ai-summary {
            background-color: #f8f9fa;
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 15px;
            border-left: 4px solid var(--primary);
        }
        
        .ai-summary-title {
            font-weight: 600;
            margin-bottom: 10px;
            color: var(--primary);
        }
        
        .ai-icon {
            color: var(--primary);
            margin-right: 8px;
        }
        
        .wordcloud-container {
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
            background-color: #f8f9fa;
            border-radius: 10px;
            margin-top: 20px;
        }
        
        .chart-container {
            position: relative;
            height: 300px;
            width: 100%;
        }
        
        .detailed-chart-container {
            position: relative;
            height: 250px;
            width: 100%;
        }
        
        .username {
            font-weight: 600;
            color: var(--primary);
        }
        
        .section-comment {
            font-size: 12px;
            padding: 5px;
            margin-bottom: 5px;
            border-radius: 5px;
            background-color: rgba(0,0,0,0.05);
        }
        
        .loading-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(255, 255, 255, 0.8);
            display: flex;
            justify-content: center;
            align-items: center;
            z-index: 9999;
        }
        
        .loading-spinner {
            border: 5px solid #f3f3f3;
            border-top: 5px solid var(--primary);
            border-radius: 50%;
            width: 50px;
            height: 50px;
            animation: spin 1s linear infinite;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .tab-container {
            margin-bottom: 20px;
        }
        
        .detailed-sentiment-legend {
            display: flex;
            justify-content: center;
            flex-wrap: wrap;
            gap: 15px;
            margin-top: 10px;
        }
        
        .legend-item {
            display: flex;
            align-items: center;
            font-size: 14px;
        }
        
        .legend-color {
            width: 16px;
            height: 16px;
            border-radius: 4px;
            margin-right: 6px;
        }
        
        .nav-link {
            color: var(--primary);
        }
        
        .nav-link:hover {
            color: var(--secondary);
        }
        
        .nav-link.active {
            color: white;
        }
        
        .abstract-summary {
            font-size: 16px;
            line-height: 1.6;
            text-align: justify;
        }
        
        .sentiment-summary {
            font-size: 15px;
            line-height: 1.5;
            text-align: justify;
        }
        
        .wordcloud-tabs {
            display: flex;
            justify-content: center;
            margin-bottom: 15px;
        }
        
        .wordcloud-tab {
            padding: 8px 16px;
            margin: 0 5px;
            border-radius: 20px 20px 0 0;
            background-color: #e9ecef;
            cursor: pointer;
            transition: all 0.3s;
        }
        
        .wordcloud-tab.active {
            background-color: var(--primary);
            color: white;
        }
        
        .wordcloud-content {
            display: none;
        }
        
        .wordcloud-content.active {
            display: block;
        }
        
        .report-button {
            position: fixed;
            bottom: 20px;
            right: 20px;
            z-index: 1000;
            background-color: var(--primary);
            color: white;
            border-radius: 50%;
            width: 60px;
            height: 60px;
            display: flex;
            justify-content: center;
            align-items: center;
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
            transition: all 0.3s;
        }
        
        .report-button:hover {
            transform: scale(1.1);
            background-color: var(--secondary);
        }
        
        .comments-section {
            margin-top: 20px;
        }
        
        .comment-item {
            margin-bottom: 15px;
            padding: 15px;
            border-radius: 8px;
            background-color: #f8f9fa;
            border-left: 4px solid var(--primary);
        }
        
        .comment-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
        }
        
        .comment-meta {
            font-size: 12px;
            color: var(--gray);
        }
        
        .comment-content {
            font-size: 14px;
            line-height: 1.5;
        }
        
        .comment-content u {
            color: var(--primary);
            font-weight: 500;
        }
        
        .pagination-container {
            display: flex;
            justify-content: center;
            margin-top: 20px;
        }
        
        .highlighted-keyword {
            color: var(--primary);
            font-weight: 500;
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <div class="dashboard-container">
        <div class="header">
            <div class="row align-items-center">
                <div class="col-md-6">
                    <h1><i class="fas fa-chart-pie me-2"></i>Sentiment Analysis</h1>
                    <p class="mb-0">Analyzing public sentiment for insights and trends</p>
                </div>
                <div class="col-md-6 text-end">
                    <div class="d-flex justify-content-end gap-2">
                        {% if 'user_id' in session %}
                            <span class="text-white me-2">Welcome, {{ session.username }}</span>
                            {% if session.is_admin %}
                                <a href="{{ url_for('generate_report') }}" class="btn btn-light" title="Generate PDF Report">
                                    <i class="fas fa-file-pdf me-1"></i> Report
                                </a>
                            {% endif %}
                            <a href="{{ url_for('logout') }}" class="btn btn-light"><i class="fas fa-sign-out-alt me-1"></i> Logout</a>
                        {% else %}
                            <a href="{{ url_for('login') }}" class="btn btn-light"><i class="fas fa-user me-1"></i> Login</a>
                        {% endif %}
                    </div>
                </div>
            </div>
        </div>
        
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
                        {{ message }}
                        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        
        {% if 'user_id' in session and not session.is_admin %}
        <div class="comment-form">
            <h5><i class="fas fa-comment me-2"></i>Submit Your Feedback</h5>
            <form method="POST" action="{{ url_for('submit_comment') }}">
                <div class="mb-3">
                    <textarea class="form-control" name="comment" rows="3" placeholder="Enter your comment here..." required></textarea>
                </div>
                <button type="submit" class="btn btn-primary">Submit Comment</button>
            </form>
        </div>
        {% elif 'user_id' not in session %}
        <div class="alert alert-info">
            <h4><i class="fas fa-info-circle me-2"></i>Access Restricted</h4>
            <p>Please log in to access the dashboard.</p>
        </div>
        {% endif %}
        
        {% if 'user_id' in session and session.is_admin %}
        <div class="row">
            <div class="col-md-8">
                <div class="card">
                    <div class="card-header">
                        <span><i class="fas fa-chart-bar me-2"></i>Feedback Analysis Overview</span>
                    </div>
                    <div class="card-body">
                        <ul class="nav nav-pills mb-3" id="sentimentTabs" role="tablist">
                            <li class="nav-item" role="presentation">
                                <button class="nav-link active" id="basic-tab" data-bs-toggle="pill" data-bs-target="#basic" type="button" role="tab" aria-controls="basic" aria-selected="true">Basic Sentiment</button>
                            </li>
                            <li class="nav-item" role="presentation">
                                <button class="nav-link" id="detailed-tab" data-bs-toggle="pill" data-bs-target="#detailed" type="button" role="tab" aria-controls="detailed" aria-selected="false">Detailed Sentiment</button>
                            </li>
                        </ul>
                        <div class="tab-content" id="sentimentTabsContent">
                            <div class="tab-pane fade show active" id="basic" role="tabpanel" aria-labelledby="basic-tab">
                                <div class="chart-container">
                                    <canvas id="sentimentChart"></canvas>
                                </div>
                            </div>
                            <div class="tab-pane fade" id="detailed" role="tabpanel" aria-labelledby="detailed-tab">
                                <div class="detailed-chart-container">
                                    <canvas id="detailedSentimentChart"></canvas>
                                </div>
                                <div class="detailed-sentiment-legend">
                                    <div class="legend-item">
                                        <div class="legend-color" style="background-color: var(--strong-positive);"></div>
                                        <span>Strong Positive</span>
                                    </div>
                                    <div class="legend-item">
                                        <div class="legend-color" style="background-color: var(--weak-positive);"></div>
                                        <span>Weak Positive</span>
                                    </div>
                                    <div class="legend-item">
                                        <div class="legend-color" style="background-color: var(--weak-negative);"></div>
                                        <span>Weak Negative</span>
                                    </div>
                                    <div class="legend-item">
                                        <div class="legend-color" style="background-color: var(--strong-negative);"></div>
                                        <span>Strong Negative</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="card">
                    <div class="card-header">
                        <i class="fas fa-map me-2"></i>Section Heat Map - Sentiment Analysis</i>
                    </div>
                    <div class="card-body">
                        <div class="heat-map">
                            <div class="heat-item heat-positive" data-section="A1: Centralization">A1: Centralization</div>
                            <div class="heat-item heat-negative" data-section="A2: Compliance">A2: Compliance</div>
                            <div class="heat-item heat-positive" data-section="A3: Transparency">A3: Transparency</div>
                            <div class="heat-item" data-section="B1: Implementation">B1: Implementation</div>
                            <div class="heat-item heat-negative" data-section="B2: Regulation">B2: Regulation</div>
                            <div class="heat-item" data-section="B3: Accountability">B3: Accountability</div>
                            <div class="heat-item heat-positive" data-section="C1: Data Rights">C1: Data Rights</div>
                            <div class="heat-item" data-section="C2: Security">C2: Security</div>
                            <div class="heat-item heat-negative" data-section="C3: Enforcement">C3: Enforcement</div>
                            <div class="heat-item" data-section="D1: Oversight">D1: Oversight</div>
                            <div class="heat-item heat-positive" data-section="D2: User Control">D2: User Control</div>
                            <div class="heat-item" data-section="D3: Breach Notification">D3: Breach Notification</div>
                        </div>
                        
                        <div class="interactive-panel">
                            <h5><i class="fas fa-info-circle me-2"></i>Section Details: <span id="selected-section">A1: Centralization</span></h5>
                            <div class="row mt-3">
                                <div class="col-md-6">
                                    <div class="card">
                                        <div class="card-body">
                                            <h6>Sentiment Distribution</h6>
                                            <canvas id="sectionChart" height="150"></canvas>
                                        </div>
                                    </div>
                                </div>
                                <div class="col-md-6">
                                    <div class="card">
                                        <div class="card-body">
                                            <h6>Key Metrics</h6>
                                            <div class="d-flex justify-content-between mb-2">
                                                <span>Positive:</span>
                                                <span class="positive" id="detail-positive">68%</span>
                                            </div>
                                            <div class="d-flex justify-content-between mb-2">
                                                <span>Negative:</span>
                                                <span class="negative" id="detail-negative">15%</span>
                                            </div>
                                            <div class="d-flex justify-content-between mb-2">
                                                <span>Neutral:</span>
                                                <span class="neutral" id="detail-neutral">17%</span>
                                            </div>
                                            <div class="d-flex justify-content-between mb-2">
                                                <span>Total Comments:</span>
                                                <span id="detail-total">142</span>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            
                            <div class="mt-3">
                                <h6>Detailed Sentiment Breakdown</h6>
                                <div class="row">
                                    <div class="col-3">
                                        <div class="text-center">
                                            <div class="metric-value strong-positive" id="detail-strong-positive">25%</div>
                                            <div class="metric-label">Strong Positive</div>
                                        </div>
                                    </div>
                                    <div class="col-3">
                                        <div class="text-center">
                                            <div class="metric-value weak-positive" id="detail-weak-positive">25%</div>
                                            <div class="metric-label">Weak Positive</div>
                                        </div>
                                    </div>
                                    <div class="col-3">
                                        <div class="text-center">
                                            <div class="metric-value weak-negative" id="detail-weak-negative">25%</div>
                                            <div class="metric-label">Weak Negative</div>
                                        </div>
                                    </div>
                                    <div class="col-3">
                                        <div class="text-center">
                                            <div class="metric-value strong-negative" id="detail-strong-negative">25%</div>
                                            <div class="metric-label">Strong Negative</div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            
                            <div class="mt-3">
                                <h6>Sample Comments</h6>
                                <div id="section-comments">
                                    <!-- Comments will be populated by JavaScript -->
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="card">
                    <div class="card-header">
                        <i class="fas fa-cloud me-2"></i>Sentiment Word Clouds</i>
                    </div>
                    <div class="card-body">
                        <div class="wordcloud-tabs">
                            <div class="wordcloud-tab active" onclick="showWordcloud('all')">All Comments</div>
                            <div class="wordcloud-tab" onclick="showWordcloud('positive')">Positive</div>
                            <div class="wordcloud-tab" onclick="showWordcloud('negative')">Negative</div>
                            <div class="wordcloud-tab" onclick="showWordcloud('neutral')">Neutral</div>
                        </div>
                        
                        <div id="all-wordcloud" class="wordcloud-content active">
                            <div class="wordcloud-container">
                                <img src="data:image/png;base64,{{ all_wordcloud_base64 }}" alt="All Comments Word Cloud" class="img-fluid rounded">
                            </div>
                        </div>
                        
                        <div id="positive-wordcloud" class="wordcloud-content">
                            <div class="wordcloud-container">
                                <img src="data:image/png;base64,{{ positive_wordcloud_base64 }}" alt="Positive Comments Word Cloud" class="img-fluid rounded">
                            </div>
                        </div>
                        
                        <div id="negative-wordcloud" class="wordcloud-content">
                            <div class="wordcloud-container">
                                <img src="data:image/png;base64,{{ negative_wordcloud_base64 }}" alt="Negative Comments Word Cloud" class="img-fluid rounded">
                            </div>
                        </div>
                        
                        <div id="neutral-wordcloud" class="wordcloud-content">
                            <div class="wordcloud-container">
                                <img src="data:image/png;base64,{{ neutral_wordcloud_base64 }}" alt="Neutral Comments Word Cloud" class="img-fluid rounded">
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="card comments-section">
                    <div class="card-header">
                        <i class="fas fa-comments me-2"></i>All Comments with Important Keywords</i>
                    </div>
                    <div class="card-body">
                        <div class="mb-3">
                            <div class="d-flex justify-content-between align-items-center">
                                <div class="filter-options">
                                    <button class="filter-btn active" onclick="filterComments('all')">All</button>
                                    <button class="filter-btn" onclick="filterComments('positive')">Positive</button>
                                    <button class="filter-btn" onclick="filterComments('negative')">Negative</button>
                                    <button class="filter-btn" onclick="filterComments('neutral')">Neutral</button>
                                </div>
                                <div class="text-muted">
                                    <i class="fas fa-info-circle me-1"></i> Important keywords are underlined
                                </div>
                            </div>
                        </div>
                        
                        <div id="comments-container">
                            {% for comment in highlighted_comments %}
                            <div class="comment-item" data-sentiment="{{ comment.sentiment }}">
                                <div class="comment-header">
                                    <div>
                                        <strong class="username">{{ comment.Username }}</strong>
                                        <span class="comment-meta">{{ comment.sentiment|capitalize }}</span>
                                        {% if comment.detailed_sentiment %}
                                        <span class="comment-meta">
                                            {% if comment.detailed_sentiment == 'strong-positive' %}Strong Positive{% elif comment.detailed_sentiment == 'weak-positive' %}Weak Positive{% elif comment.detailed_sentiment == 'weak-negative' %}Weak Negative{% else %}Strong Negative{% endif %}
                                        </span>
                                        {% endif %}
                                    </div>
                                </div>
                                <div class="comment-content">
                                    {{ comment['Comment Text']|safe }}
                                </div>
                            </div>
                            {% endfor %}
                        </div>
                        
                        <div class="pagination-container">
                            <nav aria-label="Comments pagination">
                                <ul class="pagination">
                                    <li class="page-item disabled">
                                        <a class="page-link" href="#" tabindex="-1" aria-disabled="true">Previous</a>
                                    </li>
                                    <li class="page-item active"><a class="page-link" href="#">1</a></li>
                                    <li class="page-item"><a class="page-link" href="#">2</a></li>
                                    <li class="page-item"><a class="page-link" href="#">3</a></li>
                                    <li class="page-item">
                                        <a class="page-link" href="#">Next</a>
                                    </li>
                                </ul>
                            </nav>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="col-md-4">
                <div class="card">
                    <div class="card-header">
                        <i class="fas fa-chart-line me-2"></i>Summary Metrics</i>
                    </div>
                    <div class="card-body">
                        <div class="row">
                            <div class="col-6 mb-3">
                                <div class="metric-card">
                                    <div class="metric-value positive">{{ sentiment_percentages.positive }}%</div>
                                    <div class="metric-label">Positive Sentiment</div>
                                </div>
                            </div>
                            <div class="col-6 mb-3">
                                <div class="metric-card">
                                    <div class="metric-value negative">{{ sentiment_percentages.negative }}%</div>
                                    <div class="metric-label">Negative Sentiment</div>
                                </div>
                            </div>
                            <div class="col-6 mb-3">
                                <div class="metric-card">
                                    <div class="metric-value neutral">{{ sentiment_percentages.neutral }}%</div>
                                    <div class="metric-label">Neutral Sentiment</div>
                                </div>
                            </div>
                            <div class="col-6 mb-3">
                                <div class="metric-card">
                                    <div class="metric-value">{{ total_comments }}</div>
                                    <div class="metric-label">Total Comments</div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="card">
                    <div class="card-header">
                        <i class="fas fa-file-alt me-2"></i>Abstract Summary</i>
                    </div>
                    <div class="card-body">
                        <div class="ai-summary">
                            <div class="ai-summary-title"><i class="fas fa-magic ai-icon"></i>Analysis Overview</div>
                            <p class="abstract-summary">{{ ai_summaries.abstract }}</p>
                        </div>
                    </div>
                </div>
                
                <div class="card">
                    <div class="card-header">
                        <i class="fas fa-smile me-2"></i>Positive Sentiment Summary</i>
                    </div>
                    <div class="card-body">
                        <div class="ai-summary">
                            <div class="ai-summary-title"><i class="fas fa-thumbs-up ai-icon"></i>Positive Insights</div>
                            <p class="sentiment-summary">{{ ai_summaries.positive_summary }}</p>
                        </div>
                    </div>
                </div>
                
                <div class="card">
                    <div class="card-header">
                        <i class="fas fa-frown me-2"></i>Negative Sentiment Summary</i>
                    </div>
                    <div class="card-body">
                        <div class="ai-summary">
                            <div class="ai-summary-title"><i class="fas fa-thumbs-down ai-icon"></i>Negative Insights</div>
                            <p class="sentiment-summary">{{ ai_summaries.negative_summary }}</p>
                        </div>
                    </div>
                </div>
                
                <div class="card">
                    <div class="card-header">
                        <i class="fas fa-meh me-2"></i>Neutral Sentiment Summary</i>
                    </div>
                    <div class="card-body">
                        <div class="ai-summary">
                            <div class="ai-summary-title"><i class="fas fa-balance-scale ai-icon"></i>Neutral Insights</div>
                            <p class="sentiment-summary">{{ ai_summaries.neutral_summary }}</p>
                        </div>
                    </div>
                </div>
                
                <div class="card">
                    <div class="card-header">
                        <i class="fas fa-key me-2"></i>Top Keywords</i>
                    </div>
                    <div class="card-body">
                        <div class="d-flex flex-wrap gap-2">
                            {% for keyword in top_keywords %}
                            <span class="badge bg-primary">{{ keyword }}</span>
                            {% endfor %}
                        </div>
                    </div>
                </div>
                
                <div class="card">
                    <div class="card-header">
                        <i class="fas fa-comments me-2"></i>Recent Comments</i>
                    </div>
                    <div class="card-body">
                        {% for comment in recent_comments %}
                        <div class="d-flex align-items-start mb-3">
                            <div class="me-3">
                                <div class="user-avatar bg-primary">{{ comment.Username[0].upper() }}</div>
                            </div>
                            <div class="flex-grow-1">
                                <strong class="username">{{ comment.Username }}</strong>
                                <p class="comment-text mb-1">{{ comment['Comment Text'][:80] }}{% if comment['Comment Text']|length > 80 %}...{% endif %}</p>
                                <div>
                                    <span class="sentiment-badge {% if comment.sentiment == 'positive' %}badge-positive{% elif comment.sentiment == 'negative' %}badge-negative{% else %}badge-neutral{% endif %}">
                                        {{ comment.sentiment|capitalize }}
                                    </span>
                                    {% if comment.detailed_sentiment %}
                                    <span class="sentiment-badge {% if comment.detailed_sentiment == 'strong-positive' %}badge-strong-positive{% elif comment.detailed_sentiment == 'weak-positive' %}badge-weak-positive{% elif comment.detailed_sentiment == 'weak-negative' %}badge-weak-negative{% else %}badge-strong-negative{% endif %}">
                                        {% if comment.detailed_sentiment == 'strong-positive' %}Strong Positive{% elif comment.detailed_sentiment == 'weak-positive' %}Weak Positive{% elif comment.detailed_sentiment == 'weak-negative' %}Weak Negative{% else %}Strong Negative{% endif %}
                                    </span>
                                    {% endif %}
                                </div>
                            </div>
                        </div>
                        {% endfor %}
                    </div>
                </div>
            </div>
        </div>
        {% endif %}
        
        <div class="footer">
            <div class="row">
                <div class="col-md-6">
                    <h5><i class="fas fa-coins me-2"></i>Sentiment Analysis</h5>
                    <p>Analyzing public sentiment for insights and trends</p>
                </div>
                <div class="col-md-6">
                    <h5><i class="fas fa-info-circle me-2"></i>About</h5>
                    <p>This dashboard analyzes sentiment from the dataset to understand public perception.</p>
                </div>
            </div>
        </div>
    </div>

    <!-- Preview Modal -->
    <div class="modal fade" id="previewModal" tabindex="-1" aria-labelledby="previewModalLabel" aria-hidden="true">
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title" id="previewModalLabel">Dataset Preview</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body">
                    <div class="table-responsive">
                        <table class="table table-striped">
                            <thead id="modal-preview-header"></thead>
                            <tbody id="modal-preview-body"></tbody>
                        </table>
                    </div>
                    <div id="modal-preview-info" class="mt-2"></div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                    <button type="button" class="btn btn-primary" id="confirm-upload">Confirm Upload</button>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        {% if 'user_id' in session and session.is_admin %}
        // Section sentiment data from Python
        const sectionSentimentData = {
            {% for section, data in section_sentiment.items() %}
            "{{ section }}": {
                "positive": {{ data.positive }},
                "negative": {{ data.negative }},
                "neutral": {{ data.neutral }},
                "detailed": {
                    "strong-positive": {{ data.detailed["strong-positive"] }},
                    "weak-positive": {{ data.detailed["weak-positive"] }},
                    "weak-negative": {{ data.detailed["weak-negative"] }},
                    "strong-negative": {{ data.detailed["strong-negative"] }}
                },
                "total": {{ data.total }},
                "comments": {{ data.comments|tojson }}
            },
            {% endfor %}
        };
        
        // Main Sentiment Chart
        const ctx = document.getElementById('sentimentChart').getContext('2d');
        const sentimentChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: ['Positive', 'Negative', 'Neutral'],
                datasets: [{
                    label: 'Sentiment Distribution',
                    data: [
                        {{ sentiment_percentages.positive }},
                        {{ sentiment_percentages.negative }},
                        {{ sentiment_percentages.neutral }}
                    ],
                    backgroundColor: [
                        'rgba(76, 201, 240, 0.8)',
                        'rgba(247, 37, 133, 0.8)',
                        'rgba(108, 117, 125, 0.8)'
                    ],
                    borderColor: [
                        'rgba(76, 201, 240, 1)',
                        'rgba(247, 37, 133, 1)',
                        'rgba(108, 117, 125, 1)'
                    ],
                    borderWidth: 2,
                    borderRadius: 10,
                    barThickness: 60
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: 'Overall Sentiment Analysis',
                        font: {
                            size: 18,
                            weight: 'bold'
                        },
                        padding: {
                            top: 10,
                            bottom: 30
                        }
                    },
                    legend: {
                        display: false
                    },
                    tooltip: {
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        titleFont: {
                            size: 14,
                            weight: 'bold'
                        },
                        bodyFont: {
                            size: 13
                        },
                        padding: 12,
                        cornerRadius: 8,
                        callbacks: {
                            label: function(context) {
                                return context.parsed.y + '%';
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        ticks: {
                            callback: function(value) {
                                return value + '%';
                            },
                            font: {
                                weight: 'bold'
                            }
                        },
                        grid: {
                            color: 'rgba(0, 0, 0, 0.05)'
                        }
                    },
                    x: {
                        grid: {
                            display: false
                        },
                        ticks: {
                            font: {
                                weight: 'bold',
                                size: 14
                            }
                        }
                    }
                },
                animation: {
                    duration: 2000,
                    easing: 'easeOutBounce'
                }
            }
        });
        
        // Detailed Sentiment Chart
        const detailedCtx = document.getElementById('detailedSentimentChart').getContext('2d');
        const detailedSentimentChart = new Chart(detailedCtx, {
            type: 'bar',
            data: {
                labels: ['Strong Positive', 'Weak Positive', 'Weak Negative', 'Strong Negative'],
                datasets: [{
                    label: 'Detailed Sentiment Distribution',
                    data: [
                        {{ detailed_sentiment_percentages["strong-positive"] }},
                        {{ detailed_sentiment_percentages["weak-positive"] }},
                        {{ detailed_sentiment_percentages["weak-negative"] }},
                        {{ detailed_sentiment_percentages["strong-negative"] }}
                    ],
                    backgroundColor: [
                        'rgba(46, 204, 113, 0.8)',
                        'rgba(52, 152, 219, 0.8)',
                        'rgba(243, 156, 18, 0.8)',
                        'rgba(231, 76, 60, 0.8)'
                    ],
                    borderColor: [
                        'rgba(46, 204, 113, 1)',
                        'rgba(52, 152, 219, 1)',
                        'rgba(243, 156, 18, 1)',
                        'rgba(231, 76, 60, 1)'
                    ],
                    borderWidth: 2,
                    borderRadius: 10,
                    barThickness: 50
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: 'Detailed Sentiment Analysis',
                        font: {
                            size: 18,
                            weight: 'bold'
                        },
                        padding: {
                            top: 10,
                            bottom: 30
                        }
                    },
                    legend: {
                        display: false
                    },
                    tooltip: {
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        titleFont: {
                            size: 14,
                            weight: 'bold'
                        },
                        bodyFont: {
                            size: 13
                        },
                        padding: 12,
                        cornerRadius: 8,
                        callbacks: {
                            label: function(context) {
                                return context.parsed.y + '%';
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        ticks: {
                            callback: function(value) {
                                return value + '%';
                            },
                            font: {
                                weight: 'bold'
                            }
                        },
                        grid: {
                            color: 'rgba(0, 0, 0, 0.05)'
                        }
                    },
                    x: {
                        grid: {
                            display: false
                        },
                        ticks: {
                            font: {
                                weight: 'bold',
                                size: 12
                            }
                        }
                    }
                },
                animation: {
                    duration: 2000,
                    easing: 'easeOutBounce'
                }
            }
        });
        
        // Section Chart
        const sectCtx = document.getElementById('sectionChart').getContext('2d');
        const sectionChart = new Chart(sectCtx, {
            type: 'doughnut',
            data: {
                labels: ['Positive', 'Negative', 'Neutral'],
                datasets: [{
                    data: [68, 15, 17],
                    backgroundColor: [
                        '#4cc9f0',
                        '#f72585',
                        '#6c757d'
                    ],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                cutout: '70%',
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        });
        
        // Function to update section details
        function updateSectionDetails(sectionName) {
            const sectionData = sectionSentimentData[sectionName];
            
            // Update detail metrics
            document.getElementById('detail-positive').textContent = sectionData.positive + '%';
            document.getElementById('detail-negative').textContent = sectionData.negative + '%';
            document.getElementById('detail-neutral').textContent = sectionData.neutral + '%';
            document.getElementById('detail-total').textContent = sectionData.total;
            
            // Update detailed sentiment metrics
            document.getElementById('detail-strong-positive').textContent = sectionData.detailed["strong-positive"] + '%';
            document.getElementById('detail-weak-positive').textContent = sectionData.detailed["weak-positive"] + '%';
            document.getElementById('detail-weak-negative').textContent = sectionData.detailed["weak-negative"] + '%';
            document.getElementById('detail-strong-negative').textContent = sectionData.detailed["strong-negative"] + '%';
            
            // Update section chart
            sectionChart.data.datasets[0].data = [
                sectionData.positive,
                sectionData.negative,
                sectionData.neutral
            ];
            sectionChart.update();
            
            // Update sample comments
            const commentsContainer = document.getElementById('section-comments');
            commentsContainer.innerHTML = '';
            
            if (sectionData.comments.length > 0) {
                sectionData.comments.forEach(comment => {
                    const commentDiv = document.createElement('div');
                    commentDiv.className = 'section-comment';
                    
                    const sentimentClass = comment.sentiment === 'positive' ? 'badge-positive' : 
                                          comment.sentiment === 'negative' ? 'badge-negative' : 'badge-neutral';
                    
                    let detailedSentimentHtml = '';
                    if (comment.detailed_sentiment) {
                        const detailedSentimentClass = 
                            comment.detailed_sentiment === 'strong-positive' ? 'badge-strong-positive' :
                            comment.detailed_sentiment === 'weak-positive' ? 'badge-weak-positive' :
                            comment.detailed_sentiment === 'weak-negative' ? 'badge-weak-negative' : 'badge-strong-negative';
                        
                        const detailedSentimentText = 
                            comment.detailed_sentiment === 'strong-positive' ? 'Strong Positive' :
                            comment.detailed_sentiment === 'weak-positive' ? 'Weak Positive' :
                            comment.detailed_sentiment === 'weak-negative' ? 'Weak Negative' : 'Strong Negative';
                        
                        detailedSentimentHtml = `<span class="sentiment-badge ${detailedSentimentClass}">${detailedSentimentText}</span>`;
                    }
                    
                    commentDiv.innerHTML = `
                        <strong>${comment.Username}:</strong> ${comment['Comment Text'].substring(0, 80)}${comment['Comment Text'].length > 80 ? '...' : ''}
                        <span class="sentiment-badge ${sentimentClass}">${comment.sentiment}</span>
                        ${detailedSentimentHtml}
                    `;
                    
                    commentsContainer.appendChild(commentDiv);
                });
            } else {
                commentsContainer.innerHTML = '<p class="text-muted">No comments found for this section.</p>';
            }
        }
        
        // Initialize with first section
        updateSectionDetails('A1: Centralization');
        
        // Heat map interaction
        document.querySelectorAll('.heat-item').forEach(item => {
            item.addEventListener('click', function() {
                const sectionName = this.getAttribute('data-section');
                document.getElementById('selected-section').textContent = sectionName;
                updateSectionDetails(sectionName);
            });
        });
        
        // Word cloud tab switching
        function showWordcloud(type) {
            // Hide all word clouds
            document.querySelectorAll('.wordcloud-content').forEach(content => {
                content.classList.remove('active');
            });
            
            // Remove active class from all tabs
            document.querySelectorAll('.wordcloud-tab').forEach(tab => {
                tab.classList.remove('active');
            });
            
            // Show selected word cloud
            document.getElementById(type + '-wordcloud').classList.add('active');
            
            // Add active class to selected tab
            event.target.classList.add('active');
        }
        
        // Filter comments function
        function filterComments(sentiment) {
            // Update active filter button
            document.querySelectorAll('.filter-btn').forEach(btn => {
                btn.classList.remove('active');
            });
            event.target.classList.add('active');
            
            // Show/hide comments based on sentiment
            const commentItems = document.querySelectorAll('.comment-item');
            commentItems.forEach(item => {
                if (sentiment === 'all' || item.getAttribute('data-sentiment') === sentiment) {
                    item.style.display = 'block';
                } else {
                    item.style.display = 'none';
                }
            });
        }
        {% endif %}
    </script>
</body>
</html>
"""

# Login template - Updated to remove "submit feedback" phrase
login_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - Sentiment Analysis</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        body {
            background-color: #f5f7fb;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            height: 100vh;
            display: flex;
            align-items: center;
        }
        .login-container {
            max-width: 400px;
            width: 100%;
            padding: 20px;
        }
        .card {
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        .card-header {
            background: linear-gradient(120deg, #4361ee, #3f37c9);
            color: white;
            border-radius: 10px 10px 0 0 !important;
            text-align: center;
            padding: 20px;
        }
        .btn-primary {
            background-color: #4361ee;
            border-color: #4361ee;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="row justify-content-center">
            <div class="col-md-6 login-container">
                <div class="card">
                    <div class="card-header">
                        <h4><i class="fas fa-sign-in-alt me-2"></i>Login</h4>
                    </div>
                    <div class="card-body">
                        {% with messages = get_flashed_messages(with_categories=true) %}
                            {% if messages %}
                                {% for category, message in messages %}
                                    <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
                                        {{ message }}
                                        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                                    </div>
                                {% endfor %}
                            {% endif %}
                        {% endwith %}
                        
                        <form method="POST">
                            <div class="mb-3">
                                <label for="username" class="form-label">Username</label>
                                <input type="text" class="form-control" id="username" name="username" required>
                            </div>
                            <div class="mb-3">
                                <label for="password" class="form-label">Password</label>
                                <input type="password" class="form-control" id="password" name="password" required>
                            </div>
                            <button type="submit" class="btn btn-primary w-100">Login</button>
                        </form>
                        
                        <div class="text-center mt-3">
                            <p><a href="{{ url_for('index') }}">Back to homepage</a></p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

# Register template - Updated title
register_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Register - Sentiment Analysis</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        body {
            background-color: #f5f7fb;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            height: 100vh;
            display: flex;
            align-items: center;
        }
        .register-container {
            max-width: 400px;
            width: 100%;
            padding: 20px;
        }
        .card {
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        .card-header {
            background: linear-gradient(120deg, #4361ee, #3f37c9);
            color: white;
            border-radius: 10px 10px 0 0 !important;
            text-align: center;
            padding: 20px;
        }
        .btn-primary {
            background-color: #4361ee;
            border-color: #4361ee;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="row justify-content-center">
            <div class="col-md-6 register-container">
                <div class="card">
                    <div class="card-header">
                        <h4><i class="fas fa-user-plus me-2"></i>Register</h4>
                    </div>
                    <div class="card-body">
                        {% with messages = get_flashed_messages(with_categories=true) %}
                            {% if messages %}
                                {% for category, message in messages %}
                                    <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
                                        {{ message }}
                                        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                                    </div>
                                {% endfor %}
                            {% endif %}
                        {% endwith %}
                        
                        <form method="POST">
                            <div class="mb-3">
                                <label for="username" class="form-label">Username</label>
                                <input type="text" class="form-control" id="username" name="username" required>
                            </div>
                            <div class="mb-3">
                                <label for="password" class="form-label">Password</label>
                                <input type="password" class="form-control" id="password" name="password" required>
                            </div>
                            <div class="mb-3">
                                <label for="confirm_password" class="form-label">Confirm Password</label>
                                <input type="password" class="form-control" id="confirm_password" name="confirm_password" required>
                            </div>
                            <button type="submit" class="btn btn-primary w-100">Register</button>
                        </form>
                        
                        <div class="text-center mt-3">
                            <p>Already have an account? <a href="{{ url_for('login') }}">Login here</a></p>
                            <p><a href="{{ url_for('index') }}">Back to homepage</a></p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

@app.route("/")
def index():
    # Check if user has been logged out
    if 'logout_message' in session:
        logout_message = session.pop('logout_message')
        return render_template_string(logout_template, logout_message=logout_message)
    
    is_admin = session.get('is_admin', False)
    
    if is_admin:
        # If admin hasn't uploaded data, redirect to upload page
        if df is None or sentiment_percentages is None:
            return redirect(url_for('upload_dataset_page'))
        else:
            # Show full dashboard if data is available
            return render_template_string(html_template, 
                                         sentiment_percentages=sentiment_percentages,
                                         detailed_sentiment_percentages=detailed_sentiment_percentages,
                                         total_comments=total_comments,
                                         top_keywords=top_keywords,
                                         recent_comments=recent_comments,
                                         monthly_sentiment=monthly_sentiment,
                                         ai_summaries=ai_summaries,
                                         section_sentiment=section_sentiment,
                                         all_wordcloud_base64=all_wordcloud_base64,
                                         positive_wordcloud_base64=positive_wordcloud_base64,
                                         negative_wordcloud_base64=negative_wordcloud_base64,
                                         neutral_wordcloud_base64=neutral_wordcloud_base64,
                                         highlighted_comments=highlighted_comments)
    else:
        # Regular user view
        return render_template_string(html_template, 
                                     sentiment_percentages=None,
                                     detailed_sentiment_percentages=None,
                                     total_comments=None,
                                     top_keywords=None,
                                     recent_comments=None,
                                     monthly_sentiment=None,
                                     ai_summaries=None,
                                     section_sentiment=None,
                                     all_wordcloud_base64=None,
                                     positive_wordcloud_base64=None,
                                     negative_wordcloud_base64=None,
                                     neutral_wordcloud_base64=None,
                                     highlighted_comments=None)

@app.route("/api/sentiments")
@login_required
def api_sentiments():
    return jsonify({
        "sentiment_percentages": sentiment_percentages,
        "detailed_sentiment_percentages": detailed_sentiment_percentages,
        "comments": comments_data
    })

if __name__ == "__main__":
    print("Starting Flask application...")
    app.run(debug=True)
