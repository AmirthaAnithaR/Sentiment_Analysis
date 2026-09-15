# 📊 Sentiment Analysis Web Application

A web-based **Sentiment Analysis application** built with **Python and Flask** that analyzes user comments and classifies them into **Positive, Negative, and Neutral** sentiments. The application also provides detailed sentiment analysis, keyword extraction, visualizations, user authentication, database storage, and downloadable PDF reports.

## 🚀 Features

* 🔐 **User Authentication**

  * User registration and login
  * Password hashing
  * Admin access
  * User-specific comment history

* 💬 **Sentiment Analysis**

  * Positive, Negative, and Neutral classification
  * Detailed sentiment classification:

    * Strong Positive
    * Weak Positive
    * Weak Negative
    * Strong Negative

* 📝 **Text Preprocessing**

  * Converts text to lowercase
  * Removes punctuation
  * Removes English stopwords
  * Cleans comments before analysis

* 📈 **Data Analysis & Visualization**

  * Sentiment distribution
  * Sentiment percentages
  * Sentiment analysis by user/person type
  * Monthly sentiment trends
  * Keyword frequency analysis
  * Word cloud generation

* 🤖 **Automated Summary**

  * Generates an overall sentiment summary
  * Provides separate positive, negative, and neutral summaries
  * Identifies important keywords and trends

* 📄 **PDF Reports**

  * Generate downloadable sentiment analysis reports
  * Includes analysis results and visualizations

* 💾 **Database**

  * SQLite database using Flask-SQLAlchemy
  * Stores users and submitted comments

## 🛠️ Technologies Used

* **Python**
* **Flask**
* **Flask-SQLAlchemy**
* **TextBlob**
* **NLTK**
* **Pandas**
* **NumPy**
* **Matplotlib**
* **WordCloud**
* **ReportLab**
* **SQLite**
* **HTML/CSS/JavaScript**

## 🏗️ Application Workflow

```text
User Input / Dataset
        ↓
Text Preprocessing
        ↓
Remove Punctuation & Stopwords
        ↓
TextBlob Sentiment Analysis
        ↓
Sentiment Classification
        ↓
Positive / Negative / Neutral
        ↓
Detailed Sentiment Analysis
        ↓
Statistics & Keyword Extraction
        ↓
Charts / Word Cloud / Summary
        ↓
PDF Report
```

## 📂 Project Structure

```text
Sentiment_Analysis/
│
├── app.py
├── README.md
├── comments.db
├── TaxTruth_Exploitation.csv
└── uploads/
```

> `comments.db` and generated/uploaded files may be created when the application runs.

## ⚙️ Installation

### 1. Clone the Repository

```bash
git clone https://github.com/AmirthaAnithaR/Sentiment_Analysis.git
```

### 2. Navigate to the Project

```bash
cd Sentiment_Analysis
```

### 3. Create a Virtual Environment

```bash
python -m venv venv
```

### 4. Activate the Virtual Environment

**Windows:**

```bash
venv\Scripts\activate
```

**Linux / macOS:**

```bash
source venv/bin/activate
```

### 5. Install Dependencies

```bash
pip install flask flask-sqlalchemy pandas numpy textblob nltk wordcloud matplotlib reportlab
```

### 6. Download NLTK Stopwords

The application automatically checks for the required NLTK stopwords and downloads them if they are not available.

### 7. Run the Application

```bash
python app.py
```

Open the application in your browser:

```text
http://127.0.0.1:5000
```

## 📊 Sentiment Classification

The application uses **TextBlob polarity scores** to classify comments:

| Sentiment | Condition    |
| --------- | ------------ |
| Positive  | Polarity > 0 |
| Negative  | Polarity < 0 |
| Neutral   | Polarity = 0 |

The application also provides a more detailed classification:

| Detailed Sentiment | Condition           |
| ------------------ | ------------------- |
| Strong Positive    | Polarity > 0.3      |
| Weak Positive      | 0 < Polarity ≤ 0.3  |
| Weak Negative      | -0.3 < Polarity ≤ 0 |
| Strong Negative    | Polarity ≤ -0.3     |

## 📁 Dataset

The application can analyze the `TaxTruth_Exploitation.csv` dataset.

The dataset contains information such as:

* Person type
* Profession
* Monthly income
* Tax paid
* Government benefits
* Personal comments
* Location
* Perceived tax exploitation

The application processes the comments and generates sentiment insights from the dataset.

## 📌 Example

### Input

```text
The tax system is unfair and difficult for ordinary people.
```

### Output

```text
Sentiment: Negative
Detailed Sentiment: Strong Negative
```

## 📈 Analysis Dashboard

The application provides insights such as:

* Overall sentiment distribution
* Positive/negative/neutral percentages
* Detailed sentiment distribution
* Monthly sentiment trends
* Frequently used keywords
* Sentiment by person type
* Feeling exploited distribution
* Recent comments

## 🔒 Security

The application includes:

* Password hashing using Werkzeug
* Session-based authentication
* User-specific comment storage
* Admin access control
* File upload size restrictions

> For production deployment, replace the development secret key and default credentials with secure environment-based configuration.

## 🎯 Use Cases

This project can be used for:

* Social media comment analysis
* Customer feedback analysis
* Public opinion analysis
* Survey analysis
* Tax-policy feedback analysis
* Product/service reviews
* Sentiment trend monitoring

## 🔮 Future Enhancements

* Integrate advanced NLP models such as BERT
* Add multilingual sentiment analysis
* Add real-time social media data collection
* Improve sentiment accuracy using machine learning
* Add CSV/Excel export
* Deploy using a production WSGI server
* Add interactive dashboard components
* Add Docker support

## 👩‍💻 Author

**Amirtha Anitha R**

* GitHub: [AmirthaAnithaR](https://github.com/AmirthaAnithaR)

## 📜 License

This project is developed for **educational and demonstration purposes**.
