import json
import genericMethods
import sqlFunction

from datetime import date
today = date.today()

season = "2023_2024"


def pointsThisSeason():
    points= dict()
    dbConnect = sqlFunction.connectToDB("jackbegley","Athome19369*", "" + season + "_bootstrapstatic")
    cursor = dbConnect.cursor(dictionary=True)
    cursor.execute("SELECT `second_name`, `id` FROM `" + season + "_bootstrapstatic`.`elements`")

    for row in cursor:
        secondName = row['second_name']
        cleanedSurname = str.lower(genericMethods.unicodeReplace(secondName))
        points[cleanedSurname] = row['total_points']

    return points