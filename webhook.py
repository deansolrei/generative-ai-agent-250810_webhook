"""Main webhook application for the conversational agent."""
from flask import Flask, request, jsonify
import logging
from datetime import datetime
from config import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config.from_object(Config)

@app.route('/', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'service': 'generative-ai-agent-webhook',
        'timestamp': datetime.utcnow().isoformat(),
        'version': '1.0.0'
    })

@app.route('/webhook', methods=['POST'])
def webhook_handler():
    """Main webhook endpoint for receiving messages."""
    try:
        # Get the request data
        data = request.get_json()
        
        if not data:
            logger.warning("Received empty payload")
            return jsonify({'error': 'Empty payload'}), 400
        
        logger.info(f"Received webhook data: {data}")
        
        # Extract message information
        message = data.get('message', '')
        user_id = data.get('user_id', 'unknown')
        timestamp = data.get('timestamp', datetime.utcnow().isoformat())
        
        if not message:
            logger.warning("No message found in payload")
            return jsonify({'error': 'No message provided'}), 400
        
        # Process the message (placeholder for future AI integration)
        response_message = process_message(message, user_id)
        
        # Return response
        response = {
            'success': True,
            'response': response_message,
            'user_id': user_id,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        logger.info(f"Sending response: {response}")
        return jsonify(response), 200
        
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'timestamp': datetime.utcnow().isoformat()
        }), 500

def process_message(message: str, user_id: str) -> str:
    """
    Process the incoming message and generate a response.
    
    This is a placeholder function that will be expanded with
    AI/ML capabilities in future iterations.
    
    Args:
        message (str): The incoming message text
        user_id (str): The user identifier
        
    Returns:
        str: The response message
    """
    # Simple echo response for now - will be replaced with AI logic
    response = f"Hello! I received your message: '{message}'. This is a basic webhook response that will be enhanced with AI capabilities."
    
    logger.info(f"Processed message from user {user_id}: {message[:50]}...")
    return response

@app.route('/webhook/test', methods=['GET', 'POST'])
def test_endpoint():
    """Test endpoint for webhook functionality."""
    if request.method == 'GET':
        return jsonify({
            'message': 'Webhook test endpoint is active',
            'methods': ['GET', 'POST'],
            'example_payload': {
                'message': 'Hello, webhook!',
                'user_id': 'test_user_123',
                'timestamp': datetime.utcnow().isoformat()
            }
        })
    
    # Handle POST request
    return webhook_handler()

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({
        'error': 'Endpoint not found',
        'available_endpoints': [
            'GET /',
            'POST /webhook',
            'GET|POST /webhook/test'
        ]
    }), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    logger.error(f"Internal server error: {error}")
    return jsonify({
        'error': 'Internal server error',
        'timestamp': datetime.utcnow().isoformat()
    }), 500

if __name__ == '__main__':
    logger.info("Starting webhook server...")
    app.run(
        host=app.config['HOST'],
        port=app.config['PORT'],
        debug=app.config['DEBUG']
    )