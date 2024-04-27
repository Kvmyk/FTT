from dataClass import Client as Cl
from dataService import DataServiceRestaurant as Dsr
from dbServiceClass import dbService as Dbs


clientData = Dsr(6, "Bar", "First Street", "Boston", "USA", "Nice place")


db = Dbs(clientData.dataList)

dane = db.selectData()

for i in dane:
    rating = i[1]
    place = i[2]
    street = i[3]
    city = i[4]
    country = i[5]
    desc = i[6]
    print(rating, place, street, city, country, desc)
    clientData.insertData(rating, place, street, city, country, desc)

searchResult = clientData.searchAllData("Opole", "Polska")
if searchResult != -1:
    for i in searchResult:
            print(i)    
else:
    print("Nie znaleziono")


