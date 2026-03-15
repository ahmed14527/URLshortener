

from rest_framework.throttling import UserRateThrottle, AnonRateThrottle


class URLCreateThrottle(UserRateThrottle):
   
    scope = "url_create"


class RedirectThrottle(AnonRateThrottle):
    
    scope = "anon"
