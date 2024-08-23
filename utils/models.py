
class Channel(object):
    def __init__(self, channel_obj):
        self.id = channel_obj['id']
        self.name = channel_obj.get('name', '')

    def __repr__(self):
        return '#' + self.name


class User(object):
    def __init__(self, user_info):
        self.id = user_info['id']
        self.name = user_info.get('name')
        self.email = user_info.get('email') or user_info.get('profile', {}).get('email')

    def __repr__(self):
        return '@' + self.name
