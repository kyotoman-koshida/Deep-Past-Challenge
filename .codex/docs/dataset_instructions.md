# Dataset Instructions

By far the biggest challenge in working with Akkadian / Old Assyrian texts is dealing with the formatting issues. As they say, “garbage in, garbage out” and unfortunately, the format of text in transliteration poses challenges at each step of the ML workflow, from tokenization to the transformation and embedding process.

To mitigate these issues, we provide the following information and suggestions in handling the different formatting challenges in both the transliterated and translated texts.

## Texts in Transliteration

Main formatting challenges: in addition to the standard transliteration format, with hyphenated syllables, additional scribal additions have encumbered the text with superscripts, subscripts, and punctuations only meaningful to specialists in Assyriology (Complete Transliteration Conversion Guide).

Capitalization is also a challenge, as it encodes meaning in two different ways. When the first letter of a word is capitalized it implies the word is a personal name or a place name (i.e. proper noun). When the word is in ALL CAPS, that implies it is a Sumerian logogram and was written in place of the Akkadian syllabic spelling for scribal simplicity.

Determinatives are used in Akkadian as a type of classifier for nouns and proper nouns. These signs are usually printed in superscript format adjacent to the nouns they classify. To avoid the potential confusion of reading a determinative sign as part of a work, we have followed the standard transliteration guide and retained curly brackets around these. While this may pose challenges in ML, we note that this is the only use of curly brackets in the transliteration (e.g. a-lim{ki}, A-mur-{d}UTU).

Broken text on the tablet: as these are ancient texts, they include a number of breaks and lacunae. In order to standardize these breaks, we suggest using only two markers, one for a small break of a single sign <gap> and the other for more than one sign up to large breaks <big_gap>.

For the purpose of this challenge, we include suggestions of how best to handle these formatting issues below.

## Texts in Translation

There is currently no complete or extensive database for translations of ancient cuneiform documents, and this is especially true for the Old Assyrian texts. For this reason, we gathered together the books and articles with the translations and commentaries of the Old Assyrian texts and we digitized them with an OCR and LLM for corrections. Even after all that work, there are still a number of formatting issues with these translations, which makes this a central component of the challenge for successful machine translation development.

Translations usually retain the same proper noun capitalization, and these proper nouns in general are where most ML tasks underperform. To account for these issues, we have included a lexicon in the dataset which includes all the proper nouns as specialists have normalized them for print publications.

## Modern Scribal Notations

Lastly, it is important to note that there are modern scribal notations that accompany the text in transliteration and translation. The first of these include line numbers. These are typically numbered 1, 5, 10, 15, etc. However, if there are any broken lines, the line numbers will have an apostrophe immediately following (‘), and if there is a second set of broken lines, the line numbers will have two trailing apostrophes (‘’). These are not quotation marks, but a scribal convention editors sometimes use in publication.

Additional scribal notations include:

Exclamation marks when a scholar is certain about a difficult reading of a sign !
Question mark when a scholar is uncertain about a difficult reading of a sign ?
Forward slash for when the signs belonging to a line are found below the line /
Colon for the Old Assyrian word divider sign :
Comments for breaks and erasures in parentheses ( )
Scribal insertions when a correction is made in pointy brackets < >
The demarcation of errant or erroneous signs in double pointy brackets << >>
Half brackets for partially broken signs ˹ ˺
Square brackets for clearly broken signs and lines [ ]
Curly brackets for determinatives (see below) { }

## Formatting Suggestions for Transliterations and Translations:

Remove (modern scribal notations):

! (certain reading)
? (questionable reading)
/ (line divider)
: OR . (word divider)
< > (scribal insertions, but keep the text in translit / translations)
˹ ˺ (partially broken signs, to be removed from transliteration)
[ ] (remove from document level transliteration. e.g. [KÙ.BABBAR] → KÙ.BABBAR)

Replace (breaks, gaps, superscripts, subscripts):

[x] <gap>
… <big_gap>
[… …] <big_gap>
ki {ki} (see full list below)
il5 il5 (same for any subscripted number)

Additional Characters & Formats (you may encounter):

```
Character	CDLI	ORACC	Unicode
á	a2	a₂	
à	a3	a₃	
é	e2	e₂	
è	e3	e₃	
í	i2	i₂	
ì	i3	i₃	
ú	u2	u₂	
ù	u3	u₃	
š	sz	š	U+161
Š	SZ	Š	U+160
Ṣ	s,	ṣ	U+1E63
ṣ	S,	Ṣ	U+1E62
ṭ	t,	ṭ	U+1E6D
Ṭ	T,	Ṭ	U+1E6C
‘	‘	ʾ	U+02BE
0-9	0-9	subscript ₀-₉	U+2080-U+2089
xₓ	Xx	subscript ₓ	U+208A
ḫ	h	h	U+1E2B
Ḫ	H	H	U+1E2A
```

These rows of Ḫ ḫ are here to indicate that training data (and publication data) has Ḫ ḫ but the test data has only H h.

There is only one type of H in Akkadian, so this can be a simple substitution for transliteration text Ḫ ḫ --> H h

## Akkadian determinatives in curly brackets:

{d} = dingir ‘god, deity’ — d preceding non-human divine actors
{mul} = ‘stars’ — MUL preceding astronomical bodies and constellations
{ki} = ‘earth’ — KI following a geographical place name or location
{lu₂} = LÚ preceding people and professions
{e₂} = {É} preceding buildings and institutions, such as temples and palaces
{uru} = (URU) preceding names of settlements, such as villages, towns and cities
{kur} = (KUR) preceding lands and territories as well as mountains
{mi} = munus (f) preceding feminine personal names
{m} = (1 or m) preceding masculine personal names
{geš} / {ĝeš) = (GIŠ) preceding trees and things made of wood
{tug₂} = (TÚG) preceding textiles and other woven objects
{dub} = (DUB) preceding clay tablets, and by extension, documents and legal records
{id₂} = (ÍD) (a ligature of A and ENGUR, transliterated: A.ENGUR) preceding names of canals or rivers or when written on its own referring to the divine river
{mušen} = (MUŠEN) preceding birds
{na₄} = (na4) preceding stone
{kuš} = (kuš) preceding (animal) skin, fleece, hides
{u₂} = (Ú) preceding plants

