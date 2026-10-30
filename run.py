from app import create_app
import os

app = create_app()

if __name__ == '__main__':
    app.run(debug=False, host=os.getenv('EQUIPARTS_HOST', '127.0.0.1'), port=int(os.getenv('EQUIPARTS_PORT', '5000')))
