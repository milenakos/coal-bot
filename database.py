import os

import peewee
import playhouse.postgres_ext

db = playhouse.postgres_ext.PostgresqlExtDatabase(
    'coal_bot',
    user='coal_bot',
    password=os.environ["COAL_PASS"],
    host='localhost',
    port=5432
)

class CappedIntegerField(peewee.IntegerField):
    MAX_VALUE = 2147483647
    MIN_VALUE = -2147483648

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def db_value(self, value):
        if value is not None:
            return max(self.MIN_VALUE, min(self.MAX_VALUE, value))
        return value


class Profile(peewee.Model):
    user_id = peewee.BigIntegerField()
    guild_id = peewee.BigIntegerField(index=True)

    tokens = peewee.BigIntegerField(default=0)
    clicks = peewee.BigIntegerField(default=0)
    contributions = peewee.IntegerField(default=0)

    pickaxe = peewee.CharField(default="Normal")

    inventory = playhouse.postgres_ext.BinaryJSONField(default={})

    class Meta:
        # haha facebook meta reference
        database = db
        only_save_dirty = True
        indexes = (
            (('user_id', 'guild_id'), True),
        )


class Channel(peewee.Model):
    channel_id = peewee.BigIntegerField(unique=True, index=True, primary_key=True)

    spawn_times_min = peewee.BigIntegerField(default=600)  # spawn times minimum
    spawn_times_max = peewee.BigIntegerField(default=1200)  # spawn times maximum

    yet_to_spawn = peewee.BigIntegerField(default=0)  # timestamp of the next coal, if any

    hardness_multipler = peewee.FloatField(default=1)

    class Meta:
        database = db
        only_save_dirty = True
