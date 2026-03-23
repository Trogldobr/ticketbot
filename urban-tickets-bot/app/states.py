from aiogram.fsm.state import StatesGroup, State

class TicketStates(StatesGroup):
    Idle = State()
    AwaitingScreenshot = State()
    AwaitingFullName = State()
    AwaitingAmbassador = State()
