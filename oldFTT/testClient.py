from oldFTT.dataClass import Client as Cl
from dataService import DataServiceRestaurant as Dsr
from oldFTT.dbServiceClass import dbService as Dbs
from oldFTT.serverClass import Server as Srv

clientData = Dsr(6, "Bar", "First Street", "Boston", "USA", "Nice place")

db = Dbs(clientData.dataList)

db.insertData(6, "Bar", "First Street", "Boston", "USA", "Nice place")