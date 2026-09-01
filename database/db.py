import sqlite3

DB_NAME = "wowder.db"


# ============================================================
# ПОДКЛЮЧЕНИЕ
# ============================================================

def get_connection():
    return sqlite3.connect(DB_NAME)


# ============================================================
# ИНИЦИАЛИЗАЦИЯ БАЗЫ
# ============================================================

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            username TEXT,
            full_name TEXT,
            phone TEXT,
            tour TEXT,
            tour_key TEXT DEFAULT '',
            tour_date TEXT,
            people INTEGER,
            comment TEXT,
            status TEXT DEFAULT 'Новая',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()

    # --------------------------------------------------------
    # Добавляем недостающие колонки в старую базу
    # --------------------------------------------------------

    cursor.execute("PRAGMA table_info(bookings)")
    columns = [row[1] for row in cursor.fetchall()]

    if "tour_key" not in columns:
        cursor.execute("""
            ALTER TABLE bookings
            ADD COLUMN tour_key TEXT DEFAULT ''
        """)

    if "status" not in columns:
        cursor.execute("""
            ALTER TABLE bookings
            ADD COLUMN status TEXT DEFAULT 'Новая'
        """)

    conn.commit()
    conn.close()


# ============================================================
# СОХРАНЕНИЕ ЗАЯВКИ
# ============================================================

def save_booking(data: dict):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO bookings (
            telegram_id,
            username,
            full_name,
            phone,
            tour,
            tour_key,
            tour_date,
            people,
            comment,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get("telegram_id"),
        data.get("username"),
        data.get("full_name"),
        data.get("phone"),
        data.get("tour"),
        data.get("tour_key", ""),
        data.get("tour_date"),
        data.get("people"),
        data.get("comment"),
        "Новая",
    ))

    conn.commit()
    conn.close()


# ============================================================
# ВСЕ ЗАЯВКИ
# ============================================================

def get_all_bookings():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            telegram_id,
            username,
            full_name,
            phone,
            tour,
            tour_key,
            tour_date,
            people,
            comment,
            status,
            created_at
        FROM bookings
        ORDER BY id DESC
    """)

    bookings = cursor.fetchall()

    conn.close()

    return bookings


# ============================================================
# ОДНА ЗАЯВКА
# ============================================================

def get_booking_by_id(booking_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            telegram_id,
            username,
            full_name,
            phone,
            tour,
            tour_key,
            tour_date,
            people,
            comment,
            status,
            created_at
        FROM bookings
        WHERE id = ?
    """, (booking_id,))

    booking = cursor.fetchone()

    conn.close()

    return booking


# ============================================================
# ИЗМЕНЕНИЕ СТАТУСА
# ============================================================

def update_booking_status(
    booking_id: int,
    status: str
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE bookings
        SET status = ?
        WHERE id = ?
    """, (
        status,
        booking_id,
    ))

    conn.commit()

    updated = cursor.rowcount > 0

    conn.close()

    return updated


# ============================================================
# СТАТИСТИКА
# ============================================================

def get_bookings_stats():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*)
        FROM bookings
    """)

    total = cursor.fetchone()[0]

    conn.close()

    return total


# ============================================================
# СТАТИСТИКА ПО СТАТУСАМ
# ============================================================

def get_bookings_by_status():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT status, COUNT(*)
        FROM bookings
        GROUP BY status
        ORDER BY COUNT(*) DESC
    """)

    stats = cursor.fetchall()

    conn.close()

    return stats