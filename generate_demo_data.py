import os
import random
from datetime import datetime, timedelta

import pandas as pd

ARTISTS = {
    "Taylor Swift": (12, [
        ("Anti-Hero", "USUG12300005", "Midnights"),
        ("Shake It Off", "USUG11401399", "1989"),
        ("Cruel Summer", "USUG11901162", "Lover"),
        ("Blank Space", "USUG11401400", "1989"),
        ("Love Story", "USUG11000141", "Fearless"),
        ("cardigan", "USUG12000614", "folklore"),
        ("Style", "USUG11401401", "1989"),
        ("All Too Well", "USUG11000142", "Red"),
    ]),
    "The Weeknd": (10, [
        ("Blinding Lights", "CAUM72000004", "After Hours"),
        ("Starboy", "CAUM71600019", "Starboy"),
        ("Save Your Tears", "CAUM72000010", "After Hours"),
        ("Can't Feel My Face", "CAUM71500008", "Beauty Behind the Madness"),
        ("The Hills", "CAUM71500009", "Beauty Behind the Madness"),
        ("Earned It", "CAUM71500010", "Beauty Behind the Madness"),
        ("Call Out My Name", "CAUM71800002", "My Dear Melancholy"),
    ]),
    "Dua Lipa": (8, [
        ("Levitating", "GBAHT2000023", "Future Nostalgia"),
        ("Don't Start Now", "GBAHT1900058", "Future Nostalgia"),
        ("Physical", "GBAHT2000009", "Future Nostalgia"),
        ("New Rules", "GBAHT1700073", "Dua Lipa"),
        ("Break My Heart", "GBAHT2000024", "Future Nostalgia"),
        ("One Kiss", "GBAHT1800041", "One Kiss"),
        ("Hotter than Hell", "GBAHT1600089", "Dua Lipa"),
    ]),
    "Billie Eilish": (7, [
        ("bad guy", "USUM71900764", "WHEN WE ALL FALL ASLEEP"),
        ("Happier Than Ever", "USUM72100993", "Happier Than Ever"),
        ("Ocean Eyes", "USUM71700087", "dont smile at me"),
        ("lovely", "USUM71800001", "dont smile at me"),
        ("Therefore I Am", "USUM72000891", "Therefore I Am"),
        ("when the party's over", "USUM71800892", "WHEN WE ALL FALL ASLEEP"),
    ]),
    "Harry Styles": (6, [
        ("As It Was", "GBUM72200004", "Harry's House"),
        ("Watermelon Sugar", "GBUM72000007", "Fine Line"),
        ("Adore You", "GBUM71900008", "Fine Line"),
        ("Falling", "GBUM72000009", "Fine Line"),
        ("Matilda", "GBUM72200005", "Harry's House"),
        ("Late Night Talking", "GBUM72200006", "Harry's House"),
    ]),
    "Ed Sheeran": (7, [
        ("Shape of You", "GBAHS1600463", "÷"),
        ("Perfect", "GBAHS1700117", "÷"),
        ("Thinking Out Loud", "GBAHS1400099", "x"),
        ("Bad Habits", "GBAHS2100113", "="),
        ("Photograph", "GBAHS1400100", "x"),
        ("Shivers", "GBAHS2100114", "="),
        ("Castle on the Hill", "GBAHS1600464", "÷"),
    ]),
    "Ariana Grande": (7, [
        ("7 rings", "USUM71900151", "thank u, next"),
        ("thank u, next", "USUM71900152", "thank u, next"),
        ("positions", "USUM72000891", "positions"),
        ("problem", "USUM71400234", "My Everything"),
        ("God is a woman", "USUM71800456", "Sweetener"),
        ("no tears left to cry", "USUM71800457", "Sweetener"),
        ("Side to Side", "USUM71600789", "Dangerous Woman"),
    ]),
    "Olivia Rodrigo": (6, [
        ("drivers license", "USUM72100024", "SOUR"),
        ("good 4 u", "USUM72100025", "SOUR"),
        ("deja vu", "USUM72100026", "SOUR"),
        ("brutal", "USUM72100027", "SOUR"),
        ("traitor", "USUM72100028", "SOUR"),
        ("vampire", "USUM72300041", "GUTS"),
    ]),
    "Adele": (5, [
        ("Hello", "GBBKS1500214", "25"),
        ("Someone Like You", "GBBKS1100071", "21"),
        ("Rolling in the Deep", "GBBKS1100072", "21"),
        ("Easy On Me", "GBBKS2100141", "30"),
        ("Set Fire to the Rain", "GBBKS1100073", "21"),
        ("Skyfall", "GBBKS1200112", "Skyfall"),
    ]),
    "Drake": (9, [
        ("God's Plan", "CAUM71800003", "Scorpion"),
        ("One Dance", "CAUM71600005", "Views"),
        ("Hotline Bling", "CAUM71500014", "Views"),
        ("Started From the Bottom", "CAUM71300003", "Nothing Was the Same"),
        ("Passionfruit", "CAUM71700006", "More Life"),
        ("Rich Flex", "CAUM72200001", "Her Loss"),
        ("Jimmy Cooks", "CAUM72200002", "Honestly, Nevermind"),
        ("Laugh Now Cry Later", "CAUM72000003", "Laugh Now Cry Later"),
    ]),
    "Kendrick Lamar": (7, [
        ("HUMBLE.", "USRC11700246", "DAMN."),
        ("DNA.", "USRC11700247", "DAMN."),
        ("Money Trees", "USUM71211920", "good kid, m.A.A.d city"),
        ("Alright", "USUM71500634", "To Pimp a Butterfly"),
        ("LOYALTY.", "USRC11700248", "DAMN."),
        ("Not Like Us", "USRC12400123", "Not Like Us"),
        ("Swimming Pools", "USUM71211921", "good kid, m.A.A.d city"),
    ]),
    "Travis Scott": (6, [
        ("SICKO MODE", "USRC11800576", "ASTROWORLD"),
        ("goosebumps", "USRC11700089", "Birds in the Trap Sing McKnight"),
        ("Antidote", "USRC11500612", "Rodeo"),
        ("HIGHEST IN THE ROOM", "USRC11900456", "HIGHEST IN THE ROOM"),
        ("STARGAZING", "USRC11800577", "ASTROWORLD"),
        ("Mafia", "USRC12100234", "UTOPIA"),
    ]),
    "Post Malone": (6, [
        ("Circles", "USWB11900757", "Hollywood's Bleeding"),
        ("Sunflower", "USWB11800752", "Hollywood's Bleeding"),
        ("rockstar", "USWB11700652", "beerbongs & bentleys"),
        ("White Iverson", "USWB11500234", "White Iverson"),
        ("Congratulations", "USWB11700653", "beerbongs & bentleys"),
        ("Better Now", "USWB11800753", "beerbongs & bentleys"),
    ]),
    "Kanye West": (5, [
        ("POWER", "USUM71000789", "My Beautiful Dark Twisted Fantasy"),
        ("Stronger", "USUM70700456", "Graduation"),
        ("Gold Digger", "USUM70500234", "Late Registration"),
        ("Runaway", "USUM71000790", "My Beautiful Dark Twisted Fantasy"),
        ("All Falls Down", "USUM70300123", "The College Dropout"),
        ("Flashing Lights", "USUM70700457", "Graduation"),
    ]),
    "Jay-Z": (4, [
        ("Empire State of Mind", "USUM70900456", "The Blueprint 3"),
        ("99 Problems", "USUM70400234", "The Black Album"),
        ("Run This Town", "USUM70900457", "The Blueprint 3"),
        ("Holy Grail", "USUM71300234", "Magna Carta Holy Grail"),
    ]),
    "Eminem": (5, [
        ("Lose Yourself", "USUM70200123", "8 Mile"),
        ("Slim Shady", "USUM71900891", "Music To Be Murdered By"),
        ("Without Me", "USUM70200124", "The Eminem Show"),
        ("Not Afraid", "USUM71000456", "Recovery"),
        ("Rap God", "USUM71300456", "The Marshall Mathers LP2"),
    ]),
    "21 Savage": (4, [
        ("Rockstar", "USUM71700891", "Savage Mode"),
        ("a lot", "USUM71800891", "I Am > I Was"),
        ("Bank Account", "USUM71700892", "Issa Album"),
        ("No Heart", "USUM71600891", "Savage Mode"),
    ]),
    "Orelsan": (8, [
        ("Basique", "FR9W11800587", "La Fête est Finie"),
        ("La Pluie", "FR9W11800588", "La Fête est Finie"),
        ("Civilisation", "FR9W12100421", "Civilisation"),
        ("Notes pour trop tard", "FR9W11800589", "La Fête est Finie"),
        ("L'odeur de l'essence", "FR9W12100422", "Civilisation"),
        ("San José", "FR9W12100423", "Civilisation"),
        ("Défaite de famille", "FR9W11800590", "La Fête est Finie"),
    ]),
    "PNL": (7, [
        ("Au DD", "FR9W11800021", "Deux Frères"),
        ("Jusqu'au dernier gramme", "FR9W11600122", "Dans la légende"),
        ("Naha", "FR9W11800022", "Deux Frères"),
        ("Onizuka", "FR9W11800023", "Deux Frères"),
        ("Le monde ou rien", "FR9W11600123", "Dans la légende"),
        ("Masha", "FR9W11800024", "Deux Frères"),
        ("Ça va ?", "FR9W11600124", "Dans la légende"),
    ]),
    "Nekfeu": (6, [
        ("Étoiles", "FR9W11500231", "Feu"),
        ("Cyborg", "FR9W11700341", "Les étoiles vagabondes"),
        ("Nique le monde", "FR9W11500233", "Feu"),
        ("Merci", "FR9W11500234", "Feu"),
        ("Intégral", "FR9W11700342", "Les étoiles vagabondes"),
        ("Amour sans fin", "FR9W11700343", "Les étoiles vagabondes"),
    ]),
    "SCH": (5, [
        ("LMDF", "FR9W11800301", "JVLIVS"),
        ("Surnaturel", "FR9W11800302", "JVLIVS"),
        ("Pablo", "FR9W12000401", "JVLIVS II"),
        ("Rooftop", "FR9W12000402", "JVLIVS II"),
        ("Rivière", "FR9W11800303", "JVLIVS"),
    ]),
    "Damso": (5, [
        ("Macarena", "BEF057800231", "Lithopédion"),
        ("Ipséité", "BEF057800232", "Ipséité"),
        ("Batterie faible", "BEF057800233", "Batterie faible"),
        ("Je voulais", "BEF057800234", "Lithopédion"),
        ("Mosaïque solitaire", "BEF057900235", "Lithopédion"),
    ]),
    "Vald": (5, [
        ("Désaccordé", "FR9W11700401", "NQNT2"),
        ("Soleil", "FR9W11700402", "NQNT2"),
        ("Hiver sur toute la zone", "FR9W11900501", "Agartha"),
        ("Je sais pas", "FR9W11900502", "Agartha"),
        ("Aquarium", "FR9W11900503", "Agartha"),
    ]),
    "Angèle": (4, [
        ("Balance ton quoi", "BEF057900341", "Brol"),
        ("Tout oublier", "BEF057900342", "Brol"),
        ("La loi de Murphy", "BEF057900343", "Brol"),
        ("Bruxelles je t'aime", "BEF058200444", "NONANTE-CINQ"),
    ]),
    "Arctic Monkeys": (6, [
        ("Do I Wanna Know?", "GBCEL1300091", "AM"),
        ("R U Mine?", "GBCEL1200112", "AM"),
        ("505", "GBCEL0600077", "Whatever People Say I Am"),
        ("Fluorescent Adolescent", "GBCEL1100042", "Suck It and See"),
        ("Snap Out of It", "GBCEL1300092", "AM"),
        ("Why'd You Only Call Me When You're High?", "GBCEL1300093", "AM"),
    ]),
    "Radiohead": (4, [
        ("Creep", "GBAYE9200001", "Pablo Honey"),
        ("Karma Police", "GBAYE9700002", "OK Computer"),
        ("No Surprises", "GBAYE9700003", "OK Computer"),
        ("Fake Plastic Trees", "GBAYE9500001", "The Bends"),
        ("Paranoid Android", "GBAYE9700004", "OK Computer"),
    ]),
    "Tame Impala": (5, [
        ("The Less I Know the Better", "AUUM71500012", "Currents"),
        ("Let It Happen", "AUUM71500001", "Currents"),
        ("Feels Like We Only Go Backwards", "AUUM71200008", "Lonerism"),
        ("New Person, Same Old Mistakes", "AUUM71500013", "Currents"),
        ("Eventually", "AUUM71500014", "Currents"),
    ]),
    "Red Hot Chili Peppers": (4, [
        ("Californication", "USEI19900456", "Californication"),
        ("Under the Bridge", "USEI19900457", "Blood Sugar Sex Magik"),
        ("Scar Tissue", "USEI19900458", "Californication"),
        ("Can't Stop", "USEI20020059", "By the Way"),
    ]),
    "Coldplay": (5, [
        ("The Scientist", "GBBCW0200232", "A Rush of Blood to the Head"),
        ("Yellow", "GBBCW0000235", "Parachutes"),
        ("Fix You", "GBBCW0500126", "X&Y"),
        ("Viva la Vida", "GBBCW0800186", "Viva la Vida"),
        ("A Sky Full of Stars", "GBBCW0140193", "Ghost Stories"),
    ]),
    "Gorillaz": (4, [
        ("Feel Good Inc.", "GBDUW0500012", "Demon Days"),
        ("Clint Eastwood", "GBDUW0100001", "Gorillaz"),
        ("DARE", "GBDUW0500013", "Demon Days"),
        ("On Melancholy Hill", "GBDUW1000001", "Plastic Beach"),
    ]),
    "Daft Punk": (5, [
        ("Get Lucky", "FR9W11300001", "Random Access Memories"),
        ("One More Time", "FRZ039700032", "Discovery"),
        ("Instant Crush", "FR9W11300002", "Random Access Memories"),
        ("Harder Better Faster Stronger", "FRZ039700041", "Discovery"),
        ("Around the World", "FRZ039700042", "Homework"),
        ("Within", "FR9W11300003", "Random Access Memories"),
    ]),
    "Disclosure": (4, [
        ("Latch", "GBAHT1200087", "Settle"),
        ("White Noise", "GBAHT1200088", "Settle"),
        ("You & Me", "GBAHT1400032", "Settle"),
        ("Magnets", "GBAHT1500041", "Caracal"),
    ]),
    "Calvin Harris": (4, [
        ("Summer", "GBAHS1400076", "Motion"),
        ("This Is What You Came For", "GBAHS1600233", "This Is What You Came For"),
        ("Feel So Close", "GBAHS1100098", "18 Months"),
        ("One Kiss", "GBAHS1800054", "One Kiss"),
    ]),
    "Martin Garrix": (3, [
        ("Animals", "NLF421300003", "Animals"),
        ("Scared to Be Lonely", "NLF421700001", "Scared to Be Lonely"),
        ("In the Name of Love", "NLF421600001", "In the Name of Love"),
    ]),
    "Frank Ocean": (5, [
        ("Nights", "USDJ21600008", "Blonde"),
        ("Pyramids", "USDJ21200005", "Channel ORANGE"),
        ("Thinkin Bout You", "USDJ21200001", "Channel ORANGE"),
        ("Self Control", "USDJ21600010", "Blonde"),
        ("Godspeed", "USDJ21600011", "Blonde"),
    ]),
    "SZA": (6, [
        ("Kill Bill", "USRC12200612", "SOS"),
        ("Good Days", "USRC12000835", "Good Days"),
        ("Snooze", "USRC12200613", "SOS"),
        ("Love Galore", "USRC11700312", "Ctrl"),
        ("The Weekend", "USRC11700313", "Ctrl"),
        ("Shirt", "USRC12200614", "SOS"),
    ]),
    "Beyoncé": (5, [
        ("Crazy in Love", "USQY51300009", "Dangerously in Love"),
        ("Halo", "USQY50900001", "I Am... Sasha Fierce"),
        ("Single Ladies", "USQY50900002", "I Am... Sasha Fierce"),
        ("Lemonade", "USQY51600001", "Lemonade"),
        ("CUFF IT", "USQY52200001", "RENAISSANCE"),
    ]),
    "Rihanna": (5, [
        ("Umbrella", "USQY50700001", "Good Girl Gone Bad"),
        ("We Found Love", "GBUM71101958", "Talk That Talk"),
        ("Diamonds", "USQY51200001", "Unapologetic"),
        ("Stay", "USQY51200002", "Unapologetic"),
        ("Work", "USQY51600001", "ANTI"),
    ]),
    "Amy Winehouse": (4, [
        ("Rehab", "GBAAW0600001", "Back to Black"),
        ("Back to Black", "GBAAW0600002", "Back to Black"),
        ("Valerie", "GBAAW0600003", "Back to Black"),
        ("Tears Dry on Their Own", "GBAAW0600004", "Back to Black"),
    ]),
    "Michael Jackson": (4, [
        ("Thriller", "USMO17900001", "Thriller"),
        ("Billie Jean", "USMO17900002", "Thriller"),
        ("Beat It", "USMO17900003", "Thriller"),
        ("Man in the Mirror", "USMO17900004", "Bad"),
        ("Smooth Criminal", "USMO17900005", "Bad"),
    ]),
    "Queen": (4, [
        ("Bohemian Rhapsody", "GBUM71029604", "A Night at the Opera"),
        ("Don't Stop Me Now", "GBUM71029605", "Jazz"),
        ("We Will Rock You", "GBUM71029606", "News of the World"),
        ("Somebody to Love", "GBUM71029607", "A Day at the Races"),
    ]),
    "David Bowie": (3, [
        ("Heroes", "GBAYE7900001", "Heroes"),
        ("Space Oddity", "GBAYE6900001", "Space Oddity"),
        ("Let's Dance", "GBAYE8300001", "Let's Dance"),
    ]),
    "Bad Bunny": (6, [
        ("Tití Me Preguntó", "USAT22200891", "Un Verano Sin Ti"),
        ("Me Porto Bonito", "USAT22200892", "Un Verano Sin Ti"),
        ("Ojitos Lindos", "USAT22200893", "Un Verano Sin Ti"),
        ("Moscow Mule", "USAT22200894", "Un Verano Sin Ti"),
        ("Dakiti", "USAT22000456", "El Último Tour Del Mundo"),
    ]),
    "J Balvin": (4, [
        ("Con Altura", "USRC11900234", "Con Altura"),
        ("Mi Gente", "USRC11700234", "Vibras"),
        ("Safari", "USRC11600234", "Energia"),
        ("Reggaeton", "USRC12200234", "Jose"),
    ]),
    "BTS": (5, [
        ("Dynamite", "KRUM72000001", "BE"),
        ("Boy With Luv", "KRUM71900001", "MAP OF THE SOUL: PERSONA"),
        ("DNA", "KRUM71700001", "LOVE YOURSELF: Her"),
        ("Butter", "KRUM72100001", "Butter"),
        ("Permission to Dance", "KRUM72100002", "Permission to Dance"),
    ]),
    "BLACKPINK": (4, [
        ("DDU-DU DDU-DU", "KRUM71800001", "SQUARE UP"),
        ("How You Like That", "KRUM72000002", "THE ALBUM"),
        ("Lovesick Girls", "KRUM72000003", "THE ALBUM"),
        ("Pink Venom", "KRUM72200001", "BORN PINK"),
    ]),
    "Stromae": (5, [
        ("Papaoutai", "BEF057300041", "Racine Carrée"),
        ("Alors on danse", "BEF057000012", "Cheese"),
        ("Formidable", "BEF057300042", "Racine Carrée"),
        ("L'enfer", "BEF058100341", "Multitude"),
        ("Mon amour", "BEF058100342", "Multitude"),
    ]),
    "Lorde": (3, [
        ("Royals", "NZUM71300001", "Pure Heroine"),
        ("Green Light", "NZUM71700001", "Melodrama"),
        ("Team", "NZUM71300002", "Pure Heroine"),
    ]),
    "Lana Del Rey": (4, [
        ("Summertime Sadness", "USUM71200654", "Born to Die"),
        ("Video Games", "USUM71200655", "Born to Die"),
        ("Young and Beautiful", "USUM71300456", "The Great Gatsby"),
        ("Born To Die", "USUM71200656", "Born to Die"),
    ]),
    "Khalid": (3, [
        ("Young Dumb & Broke", "USWB11700234", "American Teen"),
        ("Location", "USWB11700235", "American Teen"),
        ("Talk", "USWB11900234", "Free Spirit"),
    ]),
    "Rex Orange County": (3, [
        ("Loving is Easy", "GBUM71800001", "Pony"),
        ("Sunflower", "GBUM71800002", "Pony"),
        ("Best Friend", "GBUM71800003", "Pony"),
    ]),
}

TARGET = 10_444
today = datetime.now()
start_date = today - timedelta(days=730)

total_weight = sum(v[0] for v in ARTISTS.values())
rows = []

for artist, (weight, tracks) in ARTISTS.items():
    n = round(TARGET * weight / total_weight)
    track_weights = [1 / (i + 1) for i in range(len(tracks))]

    for _ in range(n):
        title, isrc, album = random.choices(tracks, weights=track_weights, k=1)[0]

        day_offset = random.randint(0, 729)
        date = start_date + timedelta(days=day_offset)
        hour = random.choices(range(24), weights=[
            1, 1, 1, 1, 1, 1, 2, 3, 4, 4, 4, 4, 4, 4, 4, 5, 6, 7, 8, 9, 9, 8, 6, 3
        ], k=1)[0]
        minute = random.randint(0, 59)
        second = random.randint(0, 59)
        date = date.replace(hour=hour, minute=minute, second=second)

        if random.random() < 0.15:
            duration = random.randint(10, 44)
        else:
            duration = random.randint(120, 280)

        rows.append({
            "Song Title": title,
            "Artist": artist,
            "Album Title": album,
            "ISRC": isrc,
            "Listening Time": duration,
            "Date": date.strftime("%Y-%m-%d %H:%M:%S"),
        })

while len(rows) < TARGET:
    artist = random.choice(list(ARTISTS.keys()))
    weight, tracks = ARTISTS[artist]
    title, isrc, album = random.choice(tracks)
    rows.append({
        "Song Title": title,
        "Artist": artist,
        "Album Title": album,
        "ISRC": isrc,
        "Listening Time": random.randint(120, 250),
        "Date": (start_date + timedelta(days=random.randint(0, 729))).strftime("%Y-%m-%d %H:%M:%S"),
    })
rows = rows[:TARGET]

df = pd.DataFrame(rows)
df = df.sort_values("Date", ascending=False).reset_index(drop=True)

os.makedirs("static/demo", exist_ok=True)
df.to_excel("static/demo/historique_exemple.xlsx", index=False, sheet_name="10_listeningHistory")
print(f"OK - Fichier genere : {len(df)} lignes, {df['Artist'].nunique()} artistes, {df['ISRC'].nunique()} titres uniques")
