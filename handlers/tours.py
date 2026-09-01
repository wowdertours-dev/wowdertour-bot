from aiogram import Router
from aiogram.types import CallbackQuery,InlineKeyboardMarkup,InlineKeyboardButton
from data.tours import TOURS,GUIDE,CONTACTS,KIROVSK_PROGRAM
from keyboards.main_menu import main_menu
router=Router()

def kb(key): return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📝 Оставить заявку",callback_data=f"book:{key}")],[InlineKeyboardButton(text="📅 Даты",callback_data=f"dates:{key}")],[InlineKeyboardButton(text="⬅️ Назад",callback_data="home")]])
def text(key):
 t=TOURS[key]; s=f"<b>{t['title']}</b>\n\n💰 <b>{t['price']:,} ₽</b>\n👥 До {t['capacity']} человек\n{t['transport']}\n🎯 {t['level']}\n\n<b>Входит:</b>\n".replace(',', ' ')
 s+='\n'.join('✅ '+x for x in t['includes'])+'\n\n<b>Не входит:</b>\n'+'\n'.join('• '+x for x in t['not_included'])
 return s
@router.callback_query(lambda c:c.data=="home")
async def home(c): await c.message.edit_text("🖤 <b>WowderTour</b>\n\nВыбирай направление:",reply_markup=main_menu,parse_mode="HTML"); await c.answer()
@router.callback_query(lambda c:c.data=="snow")
async def snow(c):
 k=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏂 Кировск",callback_data="tour:kirovsk")],[InlineKeyboardButton(text="🔥 Шерегеш",callback_data="tour:sheregesh")],[InlineKeyboardButton(text="⬅️ Назад",callback_data="home")]])
 await c.message.edit_text("🏂 <b>Сноуборд-туры</b>",reply_markup=k,parse_mode="HTML"); await c.answer()
@router.callback_query(lambda c:c.data.startswith("tour:"))
async def tour(c):
 key=c.data.split(':')[1]; await c.message.edit_text(text(key),reply_markup=kb(key),parse_mode="HTML"); await c.answer()
@router.callback_query(lambda c:c.data.startswith("dates:"))
async def dates(c):
 key=c.data.split(':')[1]; t=TOURS[key]; d='\n'.join('• '+x for x in t['dates']) if t['dates'] else 'Точные даты пока неизвестны. Можно оставить заявку — свяжемся при открытии набора.'
 await c.message.edit_text(f"📅 <b>{t['title']}</b>\n\n{d}",reply_markup=kb(key),parse_mode="HTML"); await c.answer()
@router.callback_query(lambda c:c.data=="about")
async def about(c): await c.message.edit_text("🖤 <b>WowderTour</b>\n\nНебольшие группы вокруг сноуборда, вейка, скейта и путешествий. Спорт, прогресс, отдых и сильное комьюнити.",reply_markup=main_menu,parse_mode="HTML"); await c.answer()
@router.callback_query(lambda c:c.data=="contacts")
async def contacts(c): await c.message.edit_text(CONTACTS,reply_markup=main_menu); await c.answer()
