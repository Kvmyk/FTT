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

db.insertData(5, "Bar", "First Street", "Boston", "USA", "Nice place")
db.insertData(4, "Bar", "Second Street", "Boston", "USA", "Nice place")
db.insertData(3, "Bar", "Third Street", "Boston", "USA", "Nice place")
db.insertData(2, "Bar", "Fourth Street", "Boston", "USA", "Nice place")
db.insertData(1, "Bar", "Fifth Street", "Boston", "USA", "Nice place")

db.selectData()