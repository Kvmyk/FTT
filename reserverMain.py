from dataClass import Client as Cl
from dataService import DataService as Ds

clientData = Ds("John", "Doe", 25, 1, "2021-12-12")
clientData.addData("Jane", "Doe", 23, 2, "2021-12-13")
clientData.addData("Jack", "Doe", 21, 3, "2021-12-14")
clientData.addData("Jill", "Doe", 22, 4, "2021-12-15")
clientData.addData("Frajer", "Kowalski", 17, 3, "2023-11-24")
clientData.sortData(clientData.dataList)
clientData.insertData("Jakub", "Kamionka", 23, 2, "2021-12-13")
clientData.showData(clientData.dataList)
clientData.removeData("Jakub", "Kamionka", 23, 2, "2021-12-13")
print("Po usunieciu")
clientData.showData(clientData.dataList)
clientData.insertData("Jakub", "Kamionka", 23, 2, "2021-12-13")
clientData.showData(clientData.dataList)