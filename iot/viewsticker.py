import re
from datetime import datetime
from django.http import JsonResponse
import random
from iot.models import DashboardNotification
from django.utils import timezone
from django.templatetags.static import static

SPECIAL_DAYS = {
    (1, 5): {
        'theme': 'newyear',
        'logo': '/static/img/newyear_logo.png',
        'message': '新年あけましておめでとうございます！今年もよろしくお願いします。'
    },
    (2, 11): {
        'theme': 'kenkokinenbi',
        'logo': '/static/img/kenkokinenbi_logo.png',
        'message': '建国記念の日です。日本の歴史に思いを馳せましょう。'
    },
    (3, 20): {
        'theme': 'shunbun',
        'logo': '/static/img/shunbun_logo.png',
        'message': '春分の日です。春の訪れを感じましょう。'
    },
    (4, 29): {
        'theme': 'showa',
        'logo': '/static/img/showa_logo.png',
        'message': '昭和の日です。歴史を振り返りましょう。'
    },
    (5, 3): {
        'theme': 'kenpoukinenbi',
        'logo': '/static/img/kenpoukinenbi_logo.png',
        'message': '憲法記念日です。平和の大切さを考えましょう。'
    },
    (5, 4): {
        'theme': 'midori',
        'logo': '/static/img/midori_logo.png',
        'message': 'みどりの日です。自然に感謝しましょう。'
    },
    (5, 5): {
        'theme': 'kodomo',
        'logo': '/static/img/kodomo_logo.png',
        'message': 'こどもの日です。子どもたちの健やかな成長を願いましょう。'
    },
    (7, 15): {
        'theme': 'umi',
        'logo': '/static/img/umi_logo.png',
        'message': '海の日です。海の恵みに感謝しましょう。'
    },
    (9, 21): {
        'theme': 'keiro',
        'logo': '/static/img/keiro_logo.png',
        'message': '敬老の日です。お年寄りに感謝の気持ちを伝えましょう。'
    },
    (9, 23): {
        'theme': 'shubun',
        'logo': '/static/img/shubun_logo.png',
        'message': '秋分の日です。秋の実りに感謝しましょう。'
    },
    (10, 10): {
        'theme': 'taiiku',
        'logo': '/static/img/taiiku_logo.png',
        'message': '体育の日です。体を動かして健康を保ちましょう。'
    },
    (11, 3): {
        'theme': 'bunka',
        'logo': '/static/img/bunka_logo.png',
        'message': '文化の日です。文化や芸術に触れましょう。'
    },
    (11, 23): {
        'theme': 'kinrou',
        'logo': '/static/img/kinrou_logo.png',
        'message': '勤労感謝の日です。働くことに感謝しましょう。'
    },
    (2, 14): {
        'theme': 'valentine',
        'logo': '/static/img/valentine_logo.png',
        'message': 'バレンタインデーです。大切な人に感謝を伝えましょう。'
    },
    (3, 3): {
        'theme': 'hinamatsuri',
        'logo': '/static/img/hinamatsuri_logo.png',
        'message': 'ひな祭りです。女の子の健やかな成長を願いましょう。'
    },
    (4, 1): {
        'theme': 'aprilfool',
        'logo': '/static/img/aprilfool_logo.png',
        'message': '今日はエイプリルフールです。冗談もほどほどに！'
    },
    (7, 7): {
        'theme': 'tanabata',
        'logo': '/static/img/tanabata_logo.png',
        'message': '今日は七夕です。願い事を短冊に書きましょう。'
    },
    (10, 31): {
        'theme': 'halloween',
        'logo': '/static/img/halloween_logo.png',
        'message': 'ハロウィンです。楽しい仮装を楽しみましょう！'
    },
    (12, 25): {
        'theme': 'christmas',
        'logo': '/static/img/christmas_logo.png',
        'message': 'メリークリスマス！素敵な一日をお過ごしください。'
    },
}

def get_japanese_greeting():
    now = datetime.now()
    hour = now.hour
    day = now.weekday()
    month = now.month
    date = now.day

    greeting = ''
    if hour < 10:
        greeting = 'おはようございます！'
    elif hour < 18:
        greeting = 'こんにちは！'
    else:
        greeting = 'こんばんは！'

    day_messages = [
        '今日は月曜日です。新しい週の始まり、頑張りましょう。',   # 0: Monday
        '今日は火曜日です。集中して作業しましょう。',           # 1: Tuesday
        '今日は水曜日です。週の真ん中、もう少しで週末です。',     # 2: Wednesday
        '今日は木曜日です。あと少しで週末です、頑張ってください！', # 3: Thursday
        '今日は金曜日です。良い週末をお過ごしください。',         # 4: Friday
        '今日は土曜日です。リラックスして楽しい一日を！',         # 5: Saturday
        '今日は日曜日です。家族と一緒に素敵な時間を過ごしましょう。' # 6: Sunday
    ]
    greeting += ' ' + day_messages[day]

    # Thêm lời chúc đặc biệt nếu là ngày đặc biệt
    special_msg = SPECIAL_DAYS.get((month, date), {}).get('message')
    if special_msg:
        greeting += ' ' + special_msg

    # Các lời chúc theo mùa
    if 3 <= month <= 5:
        greeting += ' 春の訪れです。新しいスタートを切りましょう！'
    if 6 <= month <= 8:
        greeting += ' 夏本番です。熱中症に気をつけてください。'
    if 9 <= month <= 11:
        greeting += ' 秋の気配が感じられます。体調管理に気をつけましょう。'
    if month == 12 or month <= 2:
        greeting += ' 冬の寒さが続きます。暖かくしてお過ごしください。'

    return greeting

def get_special_theme():
    now = datetime.now()
    month = now.month
    date = now.day

    for (special_month, special_date), info in SPECIAL_DAYS.items():
        if special_month == month:
            # Hiển thị trước 1 ngày hoặc đúng ngày
            if date == special_date - 1 or date == special_date:
                return {'theme': info['theme'], 'logo': info['logo']}

    return {'theme': '', 'logo': ''}

EFFECTS = [
    'fade-in-up',
    'fade-in-down',
    'fade-in-left',
    'fade-in-right',
    'pulse',
    'bounce',
    'zoom-in',
    'flip-in-x',
    'flip-in-y'
]

INSPIRATION_MESSAGES = [
    # Tháng 9/2025
    ("チームの力は、互いに助け合う姿勢によって高まる。",
    "Sức mạnh đội ngũ đến từ sự hợp tác và hỗ trợ lẫn nhau."),
    ("批判精神と素直さが揃うことで、信頼と成長が生まれる。",
     "Khi có dũng khí để nói ra và sự cởi mở để lắng nghe, mối quan hệ tin cậy, phát triển sẽ hình thành."),
    ("人生に正解はない。その時々で知恵を絞り、決断することが悔いのない人生に繋がる。",
     "Cuộc đời không có đáp án đúng, chỉ có những lựa chọn hết mình dẫn đến sự mãn nguyện."),
    ("千里の道も一歩から。今の基本が未来の力になる。",
     "Muốn đi xa, hãy bắt đầu từ bước nhỏ; những điều căn bản hôm nay là nền tảng cho ngày mai."),
    ("困難は乗り越えられる人に訪れる。だからこそ、それをチャンスと捉えよう。",
     "Khó khăn chỉ đến với người có thể vượt qua nó – hãy xem đó là cơ hội được chọn."),
    ("幸せは他人を幸せにしようとする行動から生まれる。",
     "Chỉ khi ta mang lại hạnh phúc cho người khác, ta mới thực sự cảm nhận được hạnh phúc."),
    ("ざっくりやるならやめちまえ。きっちり作ることが信頼を生む。",
     "Nếu không thể làm chỉn chu, tốt hơn là đừng làm – sự nghiêm túc tạo nên giá trị."),
    ("魚を木登りで判断するな。個性を尊重し、それぞれの強みを活かそう。",
     "Đừng đánh giá cá bằng khả năng leo cây – hãy nhìn nhận và phát huy thế mạnh riêng của mỗi người."),
    ("仲間とは、話し合い、譲り合い、赦し合い、信じ合い、想い合う関係である。",
     "Tình đồng đội được xây dựng từ sự thấu hiểu, nhường nhịn, tha thứ và niềm tin lẫn nhau."),
    ("感謝と笑顔が幸せを引き寄せる特効薬。",
     "Lòng biết ơn và nụ cười là liều thuốc đặc biệt mang lại hạnh phúc."),
    ("ゴムの木に「ハッピー」と名付け、日々の変化に気付き育てよう。",
     "Hãy đặt tên cho cây cao su là 'Hạnh phúc' và chăm sóc nó như một người bạn đồng hành."),
    ("綺麗な場所を綺麗に保つことが掃除の本質。",
     "Dọn dẹp không chỉ là làm sạch – mà là giữ gìn vẻ đẹp vốn có."),
    ("意識して3000回繰り返すことで、良き習慣が身につく。",
     "Lặp lại một việc 3000 lần sẽ biến nó thành thói quen – và thói quen tốt dẫn đến thành công."),
    ("RESPECTとは、責任・努力・戦い・向上・楽しむ・意思疎通・考えることの積み重ね。",
     "Sự tôn trọng được thể hiện qua trách nhiệm, nỗ lực, giao tiếp và tinh thần cầu tiến."),
    ("成功の反対は失敗ではなく、挑戦しないこと。",
     "Thất bại không phải là đối lập của thành công – mà là việc không dám thử."),
    ("微細なことにも真剣に取り組むことで、未来の品質が形づくられる。",
     "Chính sự nghiêm túc với những điều nhỏ nhặt sẽ định hình chất lượng trong tương lai."),

    # Tháng 10/2025 – Những bài học sâu sắc
    ("形を整えることで、心が育まれる。基本を丁寧に続けよう。",
     "Khi ta giữ gìn hình thức, tâm hồn cũng được nuôi dưỡng – hãy kiên trì với những điều căn bản."),
    ("「自分なんかダメだ」と思い込むことが一番いけない。",
     "Điều tệ nhất không phải là thất bại, mà là tin rằng mình không thể."),
    ("手放すことで新しいものが入り、挑戦することでチャンスが掴める。",
     "Buông bỏ để đón nhận mới mẻ, thay đổi để gặp gỡ, và thử thách để nắm bắt cơ hội."),
    ("嫌がる仕事を引き受け、頼まれた以上にやり、時間と約束を守る人が、なくてはならない存在になる。",
     "Người sẵn sàng làm việc khó, vượt mong đợi và giữ đúng cam kết sẽ trở thành nhân tố không thể thiếu."),
    # Tháng 11/2025 – Tin nhắn mới
    ("小さなことを怠らず積み重ねることが未来の品質を形づくる",
     "Tích lũy những điều nhỏ nhặt sẽ tạo nên chất lượng trong tương lai."),
    ("形をつくる → 形は心を創る",
     "Giữ gìn hình thức sẽ nuôi dưỡng tâm hồn."),
    ("自分を信じることが大切、「できる」と念じて生きる",
     "Tin vào bản thân và luôn nhắc mình rằng 'mình làm được'."),
    ("手放す・環境を変える・挑戦することで新しいチャンスが生まれる",
     "Buông bỏ, thay đổi môi trường, thử thách sẽ tạo ra cơ hội mới."),
    ("必要とされる人になる三大秘訣：嫌な仕事を引き受ける／頼まれた以上にやる／時間と約束を守る",
     "De trở thành người không thể thiếu: nhận việc khó, làm hơn mong đợi, giữ đúng thời gian và cam kết."),
    ("帝国ホテルの9つのテーマ：挨拶・清潔・感謝・気配り・謙虚・知識・創意・挑戦",
     "9 chủ đề của Imperial: chào hỏi, sạch sẽ, biết ơn, quan tâm, khiêm tốn, kiến thức, sáng tạo, thử thách."),
    ("今日という日は二度と来ない、今日のことは今日やり切る",
     "Ngày hôm nay sẽ không lặp lại, hãy hoàn thành việc của hôm nay trong hôm nay."),
    ("幸運は笑顔と謙虚な人に訪れる",
     "May mắn sẽ đến với người luôn mỉm cười và khiêm tốn."),
    ("思い通りにいかないからこそ人生は面白い",
     "Cuộc sống thú vị vì không phải lúc nào cũng như ý muốn."),
    ("恩は直接返せなくても「ありがとう」に変えていく",
     "Dù không thể trả ơn trực tiếp, hãy biến nó thành lời cảm ơn."),
    ("アイデアは現地現物、五感で確かめて得られる",
     "Ý tưởng đến từ thực tế, hãy dùng cả năm giác quan để kiểm chứng."),
]
def ticker_view(request):
    now = timezone.now()
    greeting = get_japanese_greeting()
    theme_info = get_special_theme()

    def rand_effect():
        return random.choice(EFFECTS)

    notifications = [{
        'type': 'greeting',
        'sender': 'SYSTEM',
        'message': greeting.strip(),
        'effect': rand_effect()
    }]
    # Shuffle toàn bộ danh sách truyền cảm hứng trước khi thêm vào notifications
    inspiration_list = list(INSPIRATION_MESSAGES)
    random.shuffle(inspiration_list)
    notifications += [
        {
            'type': 'inspiration',
            'jp': jp,
            'vi': vi,
            'effect': rand_effect(),
            'sender': 'SYSTEM'
        }
        for jp, vi in inspiration_list
    ]
    # Chỉ lấy trường cần thiết, giảm tải ORM
    mails = DashboardNotification.objects.only(
        'message', 'priority', 'is_alarm', 'sender', 'expire_at'
    ).filter(
        appear_at__lte=now, expire_at__gt=now
    ).order_by('appear_at')
    notifications += [
        {
            'type': 'mail',
            'message': notif.message,
            'priority': notif.priority,
            'is_alarm': notif.is_alarm,
            'sender': notif.sender.strip('<>').split('@')[0] if notif.sender and '@' in notif.sender else notif.sender.strip('<>'),
            'seconds_left': int((notif.expire_at - now).total_seconds())
        }
        for notif in mails
    ]

    # Nếu muốn trộn, chỉ cần random.shuffle(notifications) ở cuối
    # random.shuffle(notifications)

    default_logo = static('img/default_logo.png')
    theme = theme_info.get('theme') or 'default'
    logo = theme_info.get('logo') or default_logo

    # Lấy message đặc biệt nếu có
    month, date = now.month, now.day
    special_message = ''
    for special_month, special_date in SPECIAL_DAYS:
        if special_month == month and (date - 1) <= special_date <= (date + 3):
            special_message = SPECIAL_DAYS[(special_month, special_date)].get('message', '')
            break

    return JsonResponse({
        'greeting': greeting,
        'theme': theme,
        'logo': logo,
        'notifications': notifications,
        'special_message': special_message,
    })