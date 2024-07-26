

class MusicManager:
    def __init__(self, area):
        # This is the area the music manager belongs to
        self.area = area
        self.music = []

    def add_music(self, music):
        self.music.append(music)

    def get_music(self):
        return self.music

    def remove_music(self, music):
        self.music.remove(music)
