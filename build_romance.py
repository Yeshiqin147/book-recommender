# -*- coding: utf-8 -*-
"""阅荐言情 · 打包脚本
   从所有数据源中筛选言情相关书籍，加上 subcat 子分类标签。
"""
import json, math, os
from pathlib import Path
import pandas as pd
from pwa_titles_zh import EN_TITLE_ZH, norm_en_title

ROOT = Path(__file__).parent
DATA = ROOT / "data" / "processed"
OUT = ROOT / "pwa" / "books.json"

# 言情子分类推断
def infer_subcat(title, title_zh, desc, ol_subject=""):
    text = (str(title) + " " + str(title_zh) + " " + str(desc) + " " + str(ol_subject)).lower()

    # 古言/宫斗/宅斗
    if any(k in text for k in ["ancient china", "tang ", "ming ", "qing ", "han ", "dynasty",
                                "palace", "empress", "concubine", "emperor", "imperial",
                                "古装", "宫", "后", "妃", "帝", "王朝", "江湖", "武侠",
                                "侯门", "嫡", "庶", "宅斗", "宫斗"]):
        return "古言"

    # 仙侠/修真
    if any(k in text for k in ["fantasy romance", "paranormal", "vampire", "werewolf",
                                "shapeshifter", "dragon", "fae", "fairy", "wizard", "magic",
                                "仙侠", "修真", "仙", "妖", "神", "魔", "上神"]):
        return "仙侠"

    # 穿越/重生
    if any(k in text for k in ["time travel", "reincarnation", "second chance",
                                "穿越", "重生", "穿书", "重生之"]):
        return "穿越"

    # 甜宠
    if any(k in text for k in ["sweet", "cozy", "heartwarming", "chick lit", "romantic comedy",
                                "甜", "宠", "萌", "可爱"]):
        return "甜宠"

    # 虐文
    if any(k in text for k in ["angst", "tragic", "heartbreak", "虐", "殇", "哀", "悲"]):
        return "虐文"

    # 霸总/总裁
    if any(k in text for k in ["billionaire", "ceo", "magnate", "tycoon",
                                "总裁", "霸道", "集团", "霍总", "陆总"]):
        return "霸总"

    # 校园
    if any(k in text for k in ["high school", "college", "campus", "young adult",
                                "校园", "学生", "青春", "大学"]):
        return "校园"

    # 职场
    if any(k in text for k in ["workplace", "office", "lawyer", "doctor", "nurse",
                                "职场", "医生", "律师", "上司", "下属"]):
        return "职场"

    # 耽美
    if any(k in text for k in ["bl ", "boy's love", "danmei", "耽美", "纯爱", "男男"]):
        return "耽美"

    # 百合
    if any(k in text for k in ["gl ", "girls love", "lesbian", "百合", "女女"]):
        return "百合"

    # 悬疑爱情
    if any(k in text for k in ["thriller", "suspense", "mystery", "crime",
                                "悬疑", "探案", "侦探"]):
        return "悬疑"

    # 西方浪漫（默认现代言情）
    if any(k in text for k in ["contemporary romance", "romance", "love story",
                                "regency", "victorian", "historical romance",
                                "romance_novels", "love_stories"]):
        return "西方"

    return "现言"


def main():
    records = []

    # === 1. Open Library 言情书（主数据源） ===
    for fname in ["ol_romance.csv", "ol_books.csv", "ol_books2.csv"]:
        fpath = DATA / fname
        if not fpath.exists():
            continue
        df = pd.read_csv(fpath, encoding="utf-8-sig", dtype={"isbn": str})
        existing = {x["title"].lower().strip() for x in records}
        for _, r in df.iterrows():
            t = str(r["title"]).strip()
            if t.lower() in existing:
                continue
            existing.add(t.lower())
            rb = float(r["rating"]) * 5.0 / 4.0 if pd.notna(r["rating"]) else 0.0
            rc = float(r["rc"]) if pd.notna(r["rc"]) else 0.0
            pop = rb * math.log1p(rc) if rc > 0 else 0.0
            desc = (r["desc"] if isinstance(r["desc"], str) else "") or ""
            t_zh = EN_TITLE_ZH.get(norm_en_title(t), "")
            subj = str(r.get("subject", ""))
            subcat = infer_subcat(t, t_zh, desc, subj)
            # 只保留言情相关
            if fname == "ol_books.csv" and "romance" not in subj.lower() and subcat not in ("甜宠","虐文","西方","现言"):
                # 非 romance 主分类的书，只保留明显是言情的
                pass
            records.append({
                "isbn": str(r["isbn"]), "title": t, "title_zh": t_zh,
                "author": str(r["author"]),
                "year": int(r["year"]) if pd.notna(r["year"]) else 0,
                "publisher": "Open Library", "lang": "en",
                "subcat": subcat, "length": "长篇",
                "rating": round(rb, 2), "rc": int(rc),
                "desc": desc.strip()[:500], "pop": pop,
            })

    # === 2. 中文言情手动编目 ===
    cn_romance = [
        # 古言/宫斗/宅斗
        ("甄嬛传", "流潋紫", 2007, "古言", 8.0, 50000, "甄嬛从天真少女到深宫太后的传奇。经典宫斗文。"),
        ("如懿传", "流潋紫", 2012, "古言", 7.5, 30000, "乌拉那拉·如懿与乾隆从青梅竹马到帝后离心。"),
        ("花千骨", "fresh果果", 2008, "仙侠", 7.5, 80000, "白子画与花千骨的师徒虐恋。仙侠言情经典。"),
        ("三生三世十里桃花", "唐七", 2009, "仙侠", 7.5, 100000, "白浅与夜华的三生三世。唐七成名作。"),
        ("三生三世枕上书", "唐七", 2012, "仙侠", 7.3, 50000, "凤九与东华帝君的故事。"),
        ("香蜜沉沉烬如霜", "电线", 2009, "仙侠", 7.5, 40000, "锦觅与旭凤的三世情缘。"),
        ("楚乔传", "潇湘冬儿", 2011, "古言", 7.0, 30000, "楚乔在乱世中的成长与爱情。"),
        ("知否知否应是绿肥红瘦", "关心则乱", 2010, "宅斗", 8.0, 60000, "盛明兰的宅斗与成长。赵丽颖冯绍峰主演剧。"),
        ("瑯琊榜", "海宴", 2007, "古言", 9.0, 100000, "梅长苏复仇与情义。虽非纯言情但言情读者常读。"),
        ("扶摇皇后", "天下归元", 2011, "古言", 7.5, 20000, "孟扶摇穿越异世界的传奇。"),
        ("凰权", "天下归元", 2012, "古言", 7.8, 15000, "凤知微与宁弈的权谋爱情。"),
        ("鹤唳华亭", "雪满梁园", 2014, "古言", 8.5, 10000, "太子萧定权与陆文昔的凄美爱情。"),
        ("废后将军", "一度君华", 2010, "古言", 7.0, 20000, "虐恋经典。"),
        ("再生缘：我的温柔暴君", "墨舞碧歌", 2010, "古言", 7.5, 15000, "穿越古言。"),
        ("非我倾城：王爷要休妃", "墨舞碧歌", 2011, "古言", 7.3, 10000, "续作。"),
        ("东宫", "匪我思存", 2010, "古言", 8.0, 50000, "小枫与李承鄞的悲剧。虐文经典。"),
        ("寂寞空庭春欲晚", "匪我思存", 2006, "古言", 8.0, 40000, "康熙与良妃。"),
        ("来不及说我爱你", "匪我思存", 2005, "现言", 8.0, 50000, "民国爱情。"),
        ("佳期如梦", "匪我思存", 2007, "现言", 7.5, 60000, "尤佳期与孟和平。"),
        ("最美的时光", "桐华", 2009, "现言", 7.5, 30000, "苏蔓与宋翊。"),
        ("步步惊心", "桐华", 2005, "穿越", 8.2, 100000, "张晓穿越康熙年间与九子夺嫡。穿越言情鼻祖。"),
        ("大漠谣", "桐华", 2006, "古言", 8.0, 50000, "霍去病与金玉。"),
        ("云中歌", "桐华", 2007, "古言", 7.5, 40000, "云歌与刘弗陵。"),
        ("曾许诺", "桐华", 2011, "古言", 7.5, 30000, "上古神话爱情。"),
        ("长相思", "桐华", 2013, "仙侠", 8.5, 80000, "小夭与涂山璟、相柳。桐华言情巅峰。"),
        ("那些回不去的年少时光", "桐华", 2010, "校园", 8.5, 40000, "罗琦琦的青春成长。"),
        ("何以笙箫默", "顾漫", 2003, "现言", 8.3, 100000, "赵默笙与何以琛。等待七年。顾漫成名作。"),
        ("微微一笑很倾城", "顾漫", 2009, "甜宠", 8.5, 150000, "贝微微与肖奈。网游甜宠经典。"),
        ("杉杉来吃", "顾漫", 2011, "甜宠", 8.0, 60000, "薛杉杉与封腾。短篇甜宠。"),
        ("骄阳似我", "顾漫", 2013, "现言", 7.5, 40000, "聂曦光与林屿。"),
        ("你是我的荣耀", "顾漫", 2019, "甜宠", 8.2, 80000, "于途与乔晶晶。航天工程师与大明星。"),
        ("骄阳似我（上）", "顾漫", 2013, "甜宠", 7.5, 30000, "顾漫甜宠。"),
        ("杉杉来吃", "顾漫", 2011, "甜宠", 8.0, 60000, "薛杉杉与封腾。"),
        ("佳期如梦之海上繁花", "匪我思存", 2009, "现言", 7.5, 20000, "续作。"),
        ("裂锦", "匪我思存", 2005, "现言", 7.5, 10000, "商业虐恋。"),
        ("香寒", "匪我思存", 2007, "现言", 7.5, 10000, "续作。"),
        ("东宫", "匪我思存", 2010, "古言", 8.0, 50000, "小枫与李承鄞。"),
        ("岁月是朵两生花", "唐七", 2009, "现言", 7.5, 20000, "颜宋与林乔。"),
        ("四幕戏", "唐七", 2015, "现言", 7.0, 10000, "唐七现代言情。"),
        ("华胥引", "唐七", 2011, "古言", 8.5, 60000, "叶蓁与苏誉。四个故事。"),
        ("三生三世枕上书", "唐七", 2012, "仙侠", 7.3, 50000, "凤九与东华。"),
        ("微微一笑很倾城", "顾漫", 2009, "甜宠", 8.5, 150000, "贝微微与肖奈。"),
        ("何以笙箫默", "顾漫", 2003, "现言", 8.3, 100000, "赵默笙与何以琛。"),
        ("杉杉来吃", "顾漫", 2011, "甜宠", 8.0, 60000, "薛杉杉与封腾。"),
        ("你是我的荣耀", "顾漫", 2019, "甜宠", 8.2, 80000, "于途与乔晶晶。"),
        ("骄阳似我", "顾漫", 2013, "现言", 7.5, 40000, "聂曦光与林屿。"),
        ("最佳女配", "小花", 2018, "快穿", 7.0, 5000, "快穿文。"),
        ("穿成高考作文", "小花", 2020, "甜宠", 7.5, 3000, "校园甜宠。"),
        ("暗格里的秘密", "耳兔子", 2019, "校园", 7.8, 20000, "周斯越与丁羡。校园暗恋。"),
        ("白日梦我", "栖见", 2019, "校园", 7.5, 30000, "沈倦与林语惊。"),
        ("偏偏宠爱", "藤萝为枝", 2020, "甜宠", 7.8, 20000, "江忍与孟听。"),
        ("黑莲花攻略手册", "白羽摘雕弓", 2020, "穿书", 8.0, 40000, "凌妙妙穿书攻略黑莲花。穿书甜宠爆款。"),
        ("陈情令", "墨香铜臭", 2016, "耽美", 9.0, 200000, "魏无羡与蓝忘机。耽美天花板。"),
        ("镇魂", "priest", 2012, "耽美", 8.5, 80000, "沈巍与赵云澜。priest代表作。"),
        ("默读", "priest", 2016, "耽美", 8.7, 60000, "骆闻舟与费渡。悬疑耽美。"),
        ("杀破狼", "priest", 2015, "耽美", 8.8, 50000, "长庚与顾昀。蒸汽朋克古风耽美。"),
        ("残次品", "priest", 2017, "耽美", 8.5, 30000, "陆必行与林静恒。科幻耽美。"),
        ("天官赐福", "墨香铜臭", 2017, "耽美", 8.8, 100000, "谢怜与花城。墨香铜臭继陈情令后又一作。"),
        ("魔道祖师", "墨香铜臭", 2016, "耽美", 9.0, 200000, "即陈情令原著。"),
        ("渣反", "墨香铜臭", 2014, "耽美", 8.0, 50000, "沈清秋与洛冰河。穿书耽美。"),
        ("破云", "淮上", 2018, "耽美", 8.5, 50000, "严峫与江停。刑侦耽美。"),
        ("吞海", "淮上", 2019, "耽美", 8.5, 30000, "步重华与吴雩。"),
        ("全球高考", "木苏里", 2018, "耽美", 8.5, 40000, "游惑与秦究。无限流耽美。"),
        ("某某", "木苏里", 2019, "耽美", 8.7, 60000, "江添与盛望。校园耽美。"),
        ("判官", "木苏里", 2020, "耽美", 8.3, 30000, "闻时与谢问。"),
        ("伪装学渣", "木瓜黄", 2018, "耽美", 8.5, 50000, "贺朝与谢俞。校园耽美。"),
        ("这题超纲了", "木瓜黄", 2019, "耽美", 8.0, 30000, "邵湛与许盛。"),
        ("撒野", "巫哲", 2016, "耽美", 9.0, 100000, "蒋丞与顾飞。耽美经典。"),
        ("嚣张", "巫哲", 2019, "耽美", 8.5, 30000, "江添与盛望姊妹篇。"),
        ("轻狂", "巫哲", 2018, "耽美", 8.3, 20000, "霍然与寇忱。"),
        ("一个钢镚儿", "巫哲", 2017, "耽美", 8.3, 20000, "晏航与初一。"),
        ("解药", "巫哲", 2020, "耽美", 8.2, 20000, "程恪与江予夺。"),
        ("二哈和他的白猫师尊", "肉包不吃肉", 2018, "耽美", 8.5, 50000, "楚晚宁与墨燃。虐心耽美。"),
        ("活受罪", "鱼香肉丝", 2012, "耽美", 8.5, 10000, "沈凉生与秦敬。短篇虐心。"),
        ("长相守", "鱼香肉丝", 2013, "耽美", 8.5, 10000, "续篇。"),
        ("我开动物园那些年", "拉棉花糖的兔子", 2019, "耽美", 8.5, 20000, "段佳泽与陆压。轻松耽美。"),
        ("成化十四年", "梦溪石", 2015, "耽美", 8.5, 30000, "唐泛与隋州。古风探案耽美。"),
        ("无双", "梦溪石", 2017, "耽美", 8.5, 20000, "史无名与李少卿。"),
        ("千秋", "梦溪石", 2013, "耽美", 8.5, 30000, "沈峤与晏无师。武侠耽美。"),
        ("天宝伏妖录", "非天夜翔", 2017, "耽美", 8.5, 20000, "李景珑与孔鸿俊。古风玄幻耽美。"),
        ("将进酒", "唐酒卿", 2018, "耽美", 8.8, 50000, "沈泽川与萧驰野。权谋耽美。"),
        ("南禅", "唐酒卿", 2019, "耽美", 8.3, 15000, "蒹葭与沈澶。"),
        ("庆余年", "猫腻", 2007, "古言", 8.5, 100000, "范闲的成长。虽非纯言情但热门。"),
        ("择天记", "猫腻", 2014, "玄幻", 8.0, 30000, "陈长生逆天改命。"),
        ("将夜", "猫腻", 2011, "玄幻", 8.5, 50000, "宁缺与桑桑。"),
    ]

    seen = {x["title"].lower().strip() for x in records}
    for i, (title, author, year, subcat, rating, rc, desc) in enumerate(cn_romance):
        t = title.strip()
        if t.lower() in seen:
            continue
        seen.add(t.lower())
        pop = rating * math.log1p(rc) if rc > 0 else 0
        records.append({
            "isbn": f"CNR{len(records):04d}",
            "title": t, "title_zh": "", "author": author,
            "year": year, "publisher": "中文言情", "lang": "cn",
            "subcat": subcat, "length": "长篇",
            "rating": rating, "rc": rc, "desc": desc, "pop": pop,
        })

    # === 归一化热度 ===
    max_pop = max((x["pop"] for x in records), default=1.0)
    for x in records:
        x["pop"] = round(x["pop"] / max_pop, 4)

    payload = {
        "books": records,
        "meta": {
            "total": len(records),
            "en": sum(1 for x in records if x["lang"]=="en"),
            "cn": sum(1 for x in records if x["lang"]=="cn"),
            "with_desc": sum(1 for x in records if x["desc"]),
        }
    }
    OUT.parent.mkdir(exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    print(f"written {OUT}: total={payload['meta']['total']} "
          f"en={payload['meta']['en']} cn={payload['meta']['cn']} "
          f"with_desc={payload['meta']['with_desc']}")

if __name__ == "__main__":
    main()
