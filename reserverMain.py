from dataClass import Client as Cl
from dataService import DataServiceRestaurant as Dsr


clientData = Dsr("Joe", 6, "Bar", "First Street", "Boston", "USA")
clientData.addData("Joe", 6, "Bar", "First Street", "Boston", "USA")
clientData.addData("John", 5, "Restaurant", "Main Street", "New York", "USA")
clientData.addData("Jane", 4, "Cafe", "Second Street", "Los Angeles", "USA")
clientData.addData("Jack", 3, "Bar", "Third Street", "San Francisco", "USA")
clientData.addData("Jill", 2, "Pub", "Fourth Street", "Chicago", "USA")
clientData.addData("James", 1, "Club", "Fifth Street", "Miami", "USA")
clientData.addData("Joe", 6, "Bar", "First Street", "Boston", "USA")
clientData.addData("Joe", 6, "Bar", "First Street", "Boston", "USA")
clientData.showData(clientData.dataList)
print("Po sortowaniu")
clientData.sortData(clientData.dataList)
clientData.showData(clientData.dataList)
clientData.removeData("John", 5, "Restaurant", "Main Street", "New York", "USA")
print("Po usunięciu")
clientData.showData(clientData.dataList)
clientData.insertData("John", 5, "Restaurant", "Main Street", "New York", "USA")
print("Po dodaniu")
clientData.showData(clientData.dataList)
print("Wyszukiwanie")
clientData.sortData(clientData.dataList)

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
        