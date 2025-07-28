# Email Campaign Manager

A professional email campaign management system with Zoho CRM integration, real-time bounce detection, and advanced analytics.

## 🚀 Features

- **Zoho CRM Integration**: Send emails through Zoho CRM with OAuth2 authentication
- **Real-time Bounce Detection**: Advanced bounce detection with multi-layer fallback
- **Campaign Management**: Create, manage, and monitor email campaigns
- **Data Lists Management**: Upload and manage email lists by geo/ISP
- **Analytics Dashboard**: Real-time campaign statistics and delivery reports
- **Professional UI**: Modern, responsive web interface

## 📋 Requirements

- Python 3.8+
- Flask
- Zoho CRM Account
- Ubuntu Server (for production)

## 🛠️ Installation

### Local Development

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd email-campaign-manager
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**
   ```bash
   python app.py
   ```

4. **Access the application**
   - URL: http://localhost:5000
   - Default credentials: admin / admin123

### Production (Ubuntu Server)

1. **Server setup instructions in deployment guide**
2. **Environment configuration**
3. **SSL certificate setup**
4. **Database configuration**

## 🔧 Configuration

### Zoho CRM Setup

1. Create OAuth2 client in Zoho Developer Console
2. Configure required scopes
3. Set up bounce detection webhooks

### Data Lists

- Upload CSV files with email lists
- Organize by geography and ISP
- Import/export functionality

## 📁 Project Structure

```
email-campaign-manager/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── templates/            # HTML templates
├── static/              # CSS, JS, images
├── data_lists/          # Email lists storage
├── zoho_oauth_integration.py  # OAuth2 integration
├── zoho_bounce_integration.py # Bounce detection
└── deployment/          # Deployment scripts
```

## 🔐 Security

- OAuth2 authentication for Zoho APIs
- Secure token storage
- Input validation and sanitization
- CSRF protection

## 📊 API Endpoints

- `/api/accounts` - Account management
- `/api/campaigns` - Campaign operations
- `/api/data-lists` - Email lists management
- `/webhook/zoho/bounce` - Bounce notifications

## 🚀 Deployment

See `deployment/` directory for detailed deployment instructions.

## 📝 License

[Your License Here]

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📞 Support

For support and questions, please contact [your-email]. 