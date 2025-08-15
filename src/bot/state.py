from typing import Self

from pydantic import BaseModel


class GreenlistState(BaseModel):
    allowed_chat_ids: list[int]
    informed_chats: list[int]

    @classmethod
    def initial_state(cls) -> Self:
        return cls(
            allowed_chat_ids=[
                1365395775,
                133399998,
                1158219931,
                207651612,
                620433944,
                -1001258801123,
                -1001525369518,
                -1001635506904,
                -1001349532682,
                -1001348149915,
            ],
            informed_chats=[],
        )

    def allow(self, chat_id: int) -> None:
        if chat_id not in self.allowed_chat_ids:
            self.allowed_chat_ids.append(chat_id)

        try:
            self.informed_chats.remove(chat_id)
        except ValueError:
            pass

    def deny(self, chat_id: int) -> None:
        try:
            self.allowed_chat_ids.remove(chat_id)
        except ValueError:
            pass

    def informed_chat(self, chat_id: int) -> None:
        if chat_id not in self.informed_chats:
            self.informed_chats.append(chat_id)
