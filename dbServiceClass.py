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
        return result

    def insertData(self,rating, place, street, city, country, desc):
        ID = None
        connection = pymysql.connect(host="localhost",port = 3306, user ="root", password="", db="dbtoalety")
        cursor = connection.cursor()
        cursor.execute('INSERT INTO toalety VALUES(%s,%s, %s, %s, %s, %s, %s)', (ID,rating, place, street, city, country, desc))
        connection.commit()
        connection.close()
    
    def setID(self):
        connection = pymysql.connect(host="localhost",port = 3306, user ="root", password="", db="dbtoalety")
        cursor = connection.cursor()
        cursor.execute('SET  @num := 0;')
        cursor.execute('UPDATE toalety SET ID = @num := (@num+1);')
        cursor.execute('ALTER TABLE toalety AUTO_INCREMENT = 1;')
        connection.commit()
        connection.close()

    def deleteData(self,rating, place, street, city, country):
        connection = pymysql.connect(host="localhost",port = 3306, user ="root", password="", db="dbtoalety")
        cursor = connection.cursor()
        rows_deleted = cursor.execute('DELETE FROM toalety WHERE (rating = %s AND place = %s AND street = %s AND city = %s AND country = %s)', (rating, place, street, city, country))
        connection.commit()
        if rows_deleted == 0:
            print("No rows were deleted. Check if the record exists.")
        connection.close()
        self.setID()

    def deleteAllData(self):
        connection = pymysql.connect(host="localhost",port = 3306, user ="root", password="", db="dbtoalety")
        cursor = connection.cursor()
        cursor.execute('DELETE FROM toalety WHERE ID >= 0')
        connection.commit()
        connection.close()
        self.setID()
    