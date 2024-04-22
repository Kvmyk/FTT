from dataClass import Client as Cl
from dataService import DataServiceRestaurant as Dsr

<<<<<<< Updated upstream
clientData = Ds("Joe", 6, "Bar", "First Street", "Boston", "USA")
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
=======
clientData = Dsr("John", "Doe", 25, 1, "2021-12-12")
clientData.addData("Jane", "Doe", 23, 2, "2021-12-13")
clientData.addData("Jack", "Doe", 21, 3, "2021-12-14")
clientData.addData("Jill", "Doe", 22, 4, "2021-12-15")
clientData.addData("Frajer", "Kowalski", 17, 3, "2023-11-24")
>>>>>>> Stashed changes
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
        