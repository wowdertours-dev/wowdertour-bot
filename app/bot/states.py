from aiogram.fsm.state import State, StatesGroup


class BookingState(StatesGroup):
    choosing_tour = State()
    choosing_departure = State()
    entering_name = State()
    entering_phone = State()
    entering_people = State()
    entering_comment = State()