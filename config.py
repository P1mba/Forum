import os


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-here'

    USERS = {
        'teacher': {'password': 'teacher123', 'role': 'teacher'},
        'admin': {'password': 'admin123', 'role': 'admin'}
    }