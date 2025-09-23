# Generative AI Agent Webhook

This is the webhook for the generative AI agent - date 9-22-25

A Flask-based webhook server designed to receive and process messages for a conversational AI agent. This is a foundational implementation that can be extended with AI/ML capabilities.

## Features

- **Health Check Endpoint**: Monitor service status
- **Webhook Handler**: Process incoming messages
- **Test Endpoints**: Easy testing and development
- **Error Handling**: Comprehensive error responses
- **Logging**: Request/response logging
- **Configuration**: Environment-based configuration

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Copy the example environment file and configure:

```bash
cp .env.example .env
# Edit .env with your settings
```

### 3. Run the Webhook

```bash
python webhook.py
```

The server will start on `http://localhost:5000` by default.

## API Endpoints

### Health Check
- **GET** `/`
- Returns service status and basic information

### Webhook Handler
- **POST** `/webhook`
- Processes incoming messages
- Expected payload:
  ```json
  {
    "message": "Your message here",
    "user_id": "unique_user_id",
    "timestamp": "2023-09-22T10:00:00Z"
  }
  ```

### Test Endpoint
- **GET/POST** `/webhook/test`
- For testing webhook functionality

## Testing

Run the test script to verify functionality:

```bash
python test_webhook.py
```

## Development Roadmap

This webhook is designed to be extended step by step:

1. ✅ Basic webhook structure
2. 🔄 Message validation and processing
3. 📋 AI/ML integration for response generation
4. 📋 User session management
5. 📋 Database integration
6. 📋 Authentication and security
7. 📋 Rate limiting
8. 📋 Monitoring and analytics

## Configuration Options

Environment variables (configure in `.env`):

- `DEBUG`: Enable debug mode (default: false)
- `HOST`: Server host (default: 0.0.0.0)
- `PORT`: Server port (default: 5000)
- `SECRET_KEY`: Flask secret key
- `WEBHOOK_SECRET`: Webhook verification secret

## Deployment

### Local Development
```bash
python webhook.py
```

### Production with Gunicorn
```bash
gunicorn -w 4 -b 0.0.0.0:5000 webhook:app
```

## Contributing

This webhook is designed for step-by-step development. Each enhancement should:
- Maintain backward compatibility
- Include appropriate tests
- Update documentation
- Follow the existing code structure
