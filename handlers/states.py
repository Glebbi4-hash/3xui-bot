from aiogram.fsm.state import State, StatesGroup


class AddClientStates(StatesGroup):
    waiting_inbound  = State()   # выбор инбаунда перед созданием
    waiting_email    = State()
    waiting_traffic  = State()
    waiting_expire   = State()
