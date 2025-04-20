from dataclasses import dataclass
import json

@dataclass
class Room:
    name: str
    friends: list[str]

@dataclass
class Friend:
    nickname: str
    destination: str

@dataclass
class ChatUserConfig:
    nickname: str
    private_key: str
    sam_address: tuple[str, int]
    friends: list[Friend]
    rooms: list[Room]


def load_config_from_json() -> ChatUserConfig:
    with open("./config.json", "r") as fd:
        data = json.loads(fd.read())

    friends = [Friend(**f) for f in data["friends"]]
    rooms = [Room(**r) for r in data["rooms"]]

    return ChatUserConfig(nickname=data["nickname"],
                            private_key=data["key_file"],
                            sam_address=(data["sam_address"][0], data["sam_address"][1]),
                            friends=friends,
                            rooms=rooms
                            )