from dotenv import load_dotenv
from dotenv import find_dotenv
import os

load_dotenv(find_dotenv())

CONSUMER_KEY = os.environ.get('CONSUMER_KEY')
SHARED_SECRET = os.environ.get('SHARED_SECRET')

PYLTI_CONFIG = {
    'consumers': {
        CONSUMER_KEY: {
            'secret': SHARED_SECRET
        }
    },
    'roles': {
        'admin': ['Administrator', 'urn:lti:instrole:ims/lis/Administrator'],
        'student': ['Student', 'urn:lti:instrole:ims/lis/Student']
    }
}

configClass = 'config.Config'