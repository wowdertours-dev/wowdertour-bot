from aiogram.fsm.state import State, StatesGroup
class BookingState(StatesGroup):
 full_name=State(); phone=State(); tour_date=State(); people=State(); comment=State()
