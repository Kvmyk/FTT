from dataClass import Client as Cl
from dataService import DataServiceRestaurant as Dsr
from dbServiceClass import dbService as Dbs


clientData = Dsr(6, "Bar", "First Street", "Boston", "USA", "Nice place")

searchResult = clientData.searchData("Bar", "First Stree", "Boston", "USA")

if searchResult != -1:
    for i in searchResult:
        print(i)
else:
    searchResult = clientData.searchAllData("Bar", "First Stree", "Boston", "USA")
    if searchResult != -1:
        for i in searchResult:
            print(i)    
    else:
        print("Nie znaleziono")

db = Dbs(clientData.dataList)
db.selectData()
db.insertData("Joe", 6, "Bar", "First Street", "Boston", "USA")
print("Po dodaniu")
db.selectData()