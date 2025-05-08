# Team Recap Application

A Streamlit application for managing brand and company submissions across different platforms.

## Features

- Amazon Submission
  - Brand Name submission
  - Missing Brand submission
  - Company Name submission
- X-Amazon Submission
  - Walmart Brand submission
  - Target Brand submission
  - Home Depot Brand submission
  - Lowes Brand submission

## Local Development Setup

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `.env` file with your Snowflake credentials:
   ```
   ENV_TYPE=Test
   KEEPA_SNOWFLAKE_USER=your_username
   KEEPA_SNOWFLAKE_ACCOUNT=your_account
   KEEPA_SNOWFLAKE_WAREHOUSE=your_warehouse
   KEEPA_SNOWFLAKE_DATABASE=your_database
   KEEPA_SNOWFLAKE_SCHEMA=your_schema
   KEEPA_SNOWFLAKE_ROLE=your_role
   ```
4. Run the application:
   ```bash
   streamlit run app.py
   ```

## Deployment to GitLab and Streamlit Cloud

1. Create a GitLab repository:
   - Go to your GitLab account
   - Click "New project"
   - Choose "Create blank project"
   - Name it "team-recap"
   - Set visibility level (private recommended)
   - Click "Create project"

2. Push your code to GitLab:
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin <your-gitlab-repo-url>
   git push -u origin main
   ```

3. Set up GitLab CI/CD variables:
   - Go to Settings > CI/CD > Variables
   - Add the following variables (make them protected and masked):
     ```
     KEEPA_SNOWFLAKE_USER
     KEEPA_SNOWFLAKE_ACCOUNT
     KEEPA_SNOWFLAKE_WAREHOUSE
     KEEPA_SNOWFLAKE_DATABASE
     KEEPA_SNOWFLAKE_SCHEMA
     KEEPA_SNOWFLAKE_ROLE
     ENV_TYPE
     ```

4. Deploy to Streamlit Cloud:
   - Go to [share.streamlit.io](https://share.streamlit.io)
   - Sign in with your GitLab account
   - Click "New app"
   - Select your GitLab repository
   - Set the main file path to `app.py`
   - Add your secrets in the format:
     ```toml
     # For Test Environment
     ENV_TYPE = "Test"
     [SNOWFLAKE_CONFIG]
     user = "your_username"
     account = "your_account"
     warehouse = "your_warehouse"
     database = "your_database"
     schema = "your_schema"
     role = "your_role"
     ```
   - Click "Deploy"

## Environment Configuration

The application supports two environments:
- Test: Uses development tables (KEEPA_QUERIES_DEV, ECHO_QUERIES_DEV)
- Production: Uses production tables (KEEPA_QUERIES, ECHO_QUERIES)

To switch environments:
1. Local: Change ENV_TYPE in .env file
2. Cloud: Change ENV_TYPE in Streamlit secrets
3. GitLab: Change ENV_TYPE CI/CD variable

## Security Notes

- Never commit your `.env` file or `.streamlit/secrets.toml` to version control
- Keep your Snowflake credentials secure
- Use environment variables for sensitive information
- The app uses XSRF protection and CORS is disabled for security
- GitLab CI/CD variables are protected and masked

## Support

For any issues or questions, please contact the development team. 