"""The question set: 4 analyst conversations of 6 turns each (24 graded answers).

Each conversation keeps its full history and climbs a difficulty ladder:
easy, medium, hard, easy, expert, easy. A router that reads difficulty should escalate as
the ladder climbs and drop back on the easy follow-ups; where it starts escalating is the
router's threshold.

- easy:   one table, one filter or count
- medium: a join, an anti-join or a GROUP BY
- hard:   window functions or argmax per group, plus a data trap the question doesn't mention
- expert: a long compound ask, 3-4 dependent results in one answer, on top of the traps

The system prompt only says, for every question alike, that the data has errors to
sanity-check. Each turn has reference SQL (DuckDB); optional `tol` is the absolute tolerance
for numbers. Turns are kept only if the reference answer is unique (no ties).
"""

J = "jwst_space_images"
VALID = "date_taken <= TIMESTAMP '2026-10-05 23:59:59'"  # two photos are dated 2124
SINCE = "date_taken >= DATE '2022-07-12'"  # JWST's first images
WEBB = "('NIRCam', 'MIRI', 'NIRSpec', 'NIRISS', 'FGS')"
BIG3 = f"instrument IN {WEBB} AND instrument IN (SELECT instrument FROM {J} GROUP BY 1 HAVING count(*) >= 20)"
BURSTS = (f"WITH o AS (SELECT *, CASE WHEN date_taken - lag(date_taken) OVER (ORDER BY date_taken) > INTERVAL 7 DAY "
          f"THEN 1 ELSE 0 END AS is_new FROM {J} WHERE {VALID} AND {SINCE}), "
          "b AS (SELECT *, sum(is_new) OVER (ORDER BY date_taken ROWS UNBOUNDED PRECEDING) AS burst FROM o) ")

CONVERSATIONS = [
    {"id": "c1", "topic": "release timeline", "turns": [
        {"tier": "easy", "question": "How many images are in the published dataset?",
         "sql": f"SELECT count(*) FROM {J}"},
        {"tier": "medium", "trap": "2124 dates",
         "question": "How many of them were taken in each year from 2022 on? Return year and count.",
         "sql": f"SELECT year(date_taken) AS y, count(*) FROM {J} WHERE {VALID} AND year(date_taken) >= 2022 GROUP BY y"},
        {"tier": "hard", "trap": "gaps-and-islands; 2124 dates",
         "question": "Since JWST's first images on 2022-07-12, group published images into bursts by date_taken: an "
                     "image starts a new burst when it was taken more than 7 days (168 hours) after the previous "
                     "image. How many bursts are there, and how many images are in the largest one?",
         "sql": BURSTS + "SELECT count(DISTINCT burst), max(n) FROM (SELECT burst, count(*) AS n FROM b GROUP BY burst)"},
        {"tier": "easy", "question": "How many published images have the subject nebula?",
         "sql": f"SELECT count(*) FROM {J} WHERE subject = 'nebula'"},
        {"tier": "expert", "trap": "builds on the bursts; argmax inside a group",
         "question": "Now look at the largest of those bursts. When did it start, when did it end, how many images "
                     "does it contain, which subject is most common within it, and how many of its images have "
                     "that subject? Return start date, end date, image count, subject and subject count.",
         "sql": BURSTS + ", big AS (SELECT burst FROM b GROUP BY burst ORDER BY count(*) DESC LIMIT 1), "
                "top AS (SELECT subject, count(*) AS n FROM b WHERE burst = (SELECT burst FROM big) GROUP BY subject "
                "ORDER BY n DESC LIMIT 1) SELECT min(date_taken), max(date_taken), count(*), "
                "(SELECT subject FROM top), (SELECT n FROM top) FROM b WHERE burst = (SELECT burst FROM big)"},
        {"tier": "easy", "question": "And how many published images were taken in 2025?",
         "sql": f"SELECT count(*) FROM {J} WHERE year(date_taken) = 2025"},
    ]},
    {"id": "c2", "topic": "instruments", "turns": [
        {"tier": "easy", "question": "Which instrument values appear in the published dataset?",
         "sql": f"SELECT DISTINCT instrument FROM {J}"},
        {"tier": "medium",
         "question": "For how many published images does the instrument differ from what the labels table says?",
         "sql": f"SELECT count(*) FROM {J} j JOIN labels l USING (photo_id) WHERE j.instrument <> l.instrument"},
        {"tier": "hard", "trap": "unknown / multiple / non-Webb are not instruments; rank 2 per group",
         "question": "For each Webb instrument with at least 20 published images, which subject is the second most "
                     "common, and what percentage of that instrument's images does it account for? Return "
                     "instrument, subject and percentage (0-100) rounded to one decimal.",
         "sql": f"SELECT instrument, subject, round(100.0 * count(*) / sum(count(*)) OVER (PARTITION BY instrument), 1) "
                f"FROM {J} WHERE {BIG3} GROUP BY 1, 2 "
                "QUALIFY rank() OVER (PARTITION BY instrument ORDER BY count(*) DESC) = 2",
         "tol": 0.06},
        {"tier": "easy", "question": "How many published images list NIRSpec?",
         "sql": f"SELECT count(*) FROM {J} WHERE instrument = 'NIRSpec'"},
        {"tier": "expert", "trap": "a 2124 NIRCam image makes a 98-year gap; two denominators",
         "question": "For each of those instruments, I need three things: the longest gap in days between two "
                     "consecutive images taken since 2022-07-12, the date of the image that ended that gap, and the "
                     "percentage of all of the instrument's published images that are spectra or plots (rounded to "
                     "one decimal). Return instrument, gap, end date and percentage.",
         "sql": f"WITH g AS (SELECT instrument, date_taken, date_diff('day', lag(date_taken) OVER (PARTITION BY "
                f"instrument ORDER BY date_taken), date_taken) AS gap FROM {J} WHERE {VALID} AND {SINCE} AND {BIG3}) "
                f"SELECT instrument, gap, date_taken, (SELECT round(100.0 * count(*) FILTER (WHERE modality = "
                f"'spectrum_or_plot') / count(*), 1) FROM {J} j WHERE j.instrument = g.instrument) FROM g "
                "QUALIFY rank() OVER (PARTITION BY instrument ORDER BY gap DESC NULLS LAST) = 1",
         "tol": 1},
        {"tier": "easy", "question": "How many published images are spectra or plots?",
         "sql": f"SELECT count(*) FROM {J} WHERE modality = 'spectrum_or_plot'"},
    ]},
    {"id": "c3", "topic": "labelling pipeline", "turns": [
        {"tier": "easy", "question": "How many photos are there in total?",
         "sql": "SELECT count(*) FROM photos"},
        {"tier": "medium", "question": "How many photos have never been labelled?",
         "sql": "SELECT count(*) FROM photos p WHERE NOT EXISTS (SELECT 1 FROM labels l WHERE l.photo_id = p.photo_id)"},
        {"tier": "hard", "trap": "'galaxy cluster' vs 'galaxy_cluster'; denominator",
         "question": "photos.legacy_tag_label comes from an older keyword classifier. Among labelled photos whose "
                     "legacy label names an astronomical subject (anything except 'unclassified' and "
                     "'observatory / engineering'), what percentage got the same subject from the model? "
                     "Give a percentage (0-100) rounded to one decimal.",
         "sql": "SELECT round(100.0 * count(*) FILTER (WHERE replace(p.legacy_tag_label, ' ', '_') = l.subject) "
                "/ count(*), 1) FROM photos p JOIN labels l USING (photo_id) "
                "WHERE p.legacy_tag_label NOT IN ('unclassified', 'observatory / engineering')",
         "tol": 0.06},
        {"tier": "easy", "question": "How many labels were made with codebook version v6?",
         "sql": "SELECT count(*) FROM labels WHERE codebook_version = 'v6'"},
        {"tier": "expert", "trap": "left join for unpublished; argmax per year among a subset",
         "question": "Break the labelling outcome down by year, for photos taken from 2022 through 2025. For each "
                     "year I want the number of labelled photos taken that year, the percentage of them that did "
                     "not make it into the published dataset (rounded to one decimal), and the gate_category that "
                     "was most common among the ones that didn't make it. Return year, labelled count, percentage "
                     "and gate category.",
         "sql": f"WITH t AS (SELECT year(p.date_taken) AS y, l.gate_category AS g, j.photo_id IS NULL AS rej "
                f"FROM photos p JOIN labels l USING (photo_id) LEFT JOIN {J} j USING (photo_id) "
                "WHERE year(p.date_taken) BETWEEN 2022 AND 2025), "
                "m AS (SELECT y, g FROM t WHERE rej GROUP BY y, g QUALIFY rank() OVER (PARTITION BY y ORDER BY count(*) DESC) = 1) "
                "SELECT t.y, count(*), round(100.0 * avg(rej::int), 1), any_value(m.g) FROM t JOIN m USING (y) GROUP BY t.y",
         "tol": 0.06},
        {"tier": "easy", "question": "How many photos have no tags at all?",
         "sql": "SELECT count(*) FROM photos WHERE tags IS NULL OR len(tags) = 0"},
    ]},
    {"id": "c4", "topic": "objects", "turns": [
        {"tier": "easy", "question": "How many published images have no object name?",
         "sql": f"SELECT count(*) FROM {J} WHERE object_name IS NULL"},
        {"tier": "medium", "question": "Using object_name_normalized, which 5 objects appear most often? "
                                       "Return object and count.",
         "sql": f"SELECT object_name_normalized, count(*) AS n FROM {J} WHERE object_name_normalized IS NOT NULL "
                "GROUP BY 1 ORDER BY n DESC LIMIT 5"},
        {"tier": "hard", "trap": "a 2124 Jupiter date makes Jupiter the wrong winner",
         "question": "Among objects with at least 4 published images, which one has the longest span between its "
                     "first and last image, and how many days is that span?",
         "sql": f"SELECT object_name_normalized, date_diff('day', min(date_taken), max(date_taken)) AS span FROM {J} "
                f"WHERE {VALID} AND object_name_normalized IS NOT NULL GROUP BY 1 HAVING count(*) >= 4 "
                "ORDER BY span DESC LIMIT 1",
         "tol": 1},
        {"tier": "easy", "question": "How many published images show the Pillars of Creation?",
         "sql": f"SELECT count(*) FROM {J} WHERE object_name_normalized = 'Pillars of Creation'"},
        {"tier": "expert", "trap": "spellings split objects; 2124 Jupiter date; not-a-single-instrument values",
         "question": "Which objects have published images taken in at least 3 different calendar years? For each "
                     "one, give the number of images, the first and last year it was imaged, and the percentage of "
                     "its images attributed to exactly one named Webb instrument (rounded to one decimal). Return "
                     "object, image count, first year, last year and percentage.",
         "sql": f"SELECT object_name_normalized, count(*), min(year(date_taken)), max(year(date_taken)), "
                f"round(100.0 * count(*) FILTER (WHERE instrument IN {WEBB}) / count(*), 1) FROM {J} "
                f"WHERE {VALID} AND object_name_normalized IS NOT NULL GROUP BY 1 "
                "HAVING count(DISTINCT year(date_taken)) >= 3",
         "tol": 0.06},
        {"tier": "easy", "question": "How many published images show Jupiter?",
         "sql": f"SELECT count(*) FROM {J} WHERE object_name_normalized = 'Jupiter'"},
    ]},
]


def conversations():
    """Every conversation with turn ids like c1.3."""
    return [{**c, "turns": [{"id": f"{c['id']}.{i}", **t} for i, t in enumerate(c["turns"], 1)]}
            for c in CONVERSATIONS]


TURNS = {t["id"]: t for c in conversations() for t in c["turns"]}
