from tools.server import app

# This file serves as the WSGI entrypoint for deployment platforms 
# like Vercel, Render, Heroku, or PythonAnywhere.
# The platform will look for 'app' inside 'app.py'.

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
