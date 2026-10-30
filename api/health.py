"""Simple health check endpoint to test if Vercel Python functions work at all"""

def handler(event, context):
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': '{"status": "ok", "message": "Vercel function works"}'
    }
