import os

CONSUMER_KEY = os.environ.get('CONSUMER_KEY', 'aBQPx3TvPa52ldxDIjakZwJchc4dGBUG')
SHARED_SECRET = os.environ.get('SHARED_SECRET', 'yqPWJQzzjKrZpG5M9o6a6Zjo24zzyMuR')

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

secret_key = os.environ.get('SECRET_FLASK', 'UnlQT4jNL5U3IGpegm2ALgnKfZHnPBaa')
configClass = 'config.DevelopmentConfig'