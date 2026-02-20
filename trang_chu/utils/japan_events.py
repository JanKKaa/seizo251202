import datetime

def get_japan_event():
    today = datetime.date.today()
    check_date = today  # Sửa lại: kiểm tra đúng ngày hôm nay

    # お正月 (Tết Dương lịch, 1/1)
    if check_date.month == 1 and check_date.day == 1:
        return 'oshougatsu'
    # 成人の日 (thứ 2 tuần thứ 2 tháng 1)
    if check_date.month == 1 and check_date.weekday() == 0:
        # Tìm thứ 2 tuần thứ 2
        if 8 <= check_date.day <= 14:
            return 'seijin'
    # 建国記念の日 (11/2)
    if check_date.month == 2 and check_date.day == 11:
        return 'kenkoku'
    # ひな祭り (3/3)
    if check_date.month == 3 and check_date.day == 3:
        return 'hinamatsuri'
    # ゴールデンウィーク (29/4~5/5)
    if (check_date.month == 4 and check_date.day >= 29) or (check_date.month == 5 and check_date.day <= 5):
        return 'goldenweek'
    # 七夕 (7/7)
    if check_date.month == 7 and check_date.day == 7:
        return 'tanabata'
    # お盆 (giữa tháng 8, lấy 13~16/8)
    if check_date.month == 8 and 13 <= check_date.day <= 16:
        return 'obon'
    # 敬老の日 (thứ 2 tuần thứ 3 tháng 9)
    if check_date.month == 9 and check_date.weekday() == 0:
        if 15 <= check_date.day <= 21:
            return 'keirou'
    # 秋分の日 (23/9)
    if check_date.month == 9 and check_date.day == 23:
        return 'shubun'
    # 文化の日 (3/11)
    if check_date.month == 11 and check_date.day == 3:
        return 'bunka'
    # クリスマス (25/12)
    if check_date.month == 12 and check_date.day == 25:
        return 'christmas'
    return None