from dataService import DataServiceRestaurant as Dsr
import pymysql

class dbService(Dsr):
    def __init__(self, dataList):
        self.dataList = dataList
    
    def __str__(self):
        return self.dataList
    
    def selectData(self):
        connection = pymysql.connect(host="localhost",port = 3306, user ="root", password="", db="dbtoalety")
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM toalety")
        result = cursor.fetchall()
        for i in result:
            print(i)
        connection.close()

    def insertData(self, nickName, rating, place, street, city, country):
        connection = pymysql.connect(host="localhost",port = 3306, user ="root", password="", db="dbtoalety")
        cursor = connection.cursor()
        cursor.execute('INSERT INTO toalety VALUES(%s, %s, %s, %s, %s, %s)', (nickName, rating, place, street, city, country))
        connection.commit()
        connection.close()
    
    def deleteData(self, nickName, rating, place, street, city, country):
        connection = pymysql.connect(host="localhost",port = 3306, user ="root", password="", db="dbtoalety")
        cursor = connection.cursor()
        rows_deleted = cursor.execute('DELETE FROM toalety WHERE (nickName = %s AND rating = %s AND place = %s AND street = %s AND city = %s AND country = %s)', (nickName, rating, place, street, city, country))
        connection.commit()
        if rows_deleted == 0:
            print("No rows were deleted. Check if the record exists.")
        connection.close()