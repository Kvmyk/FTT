def findMedianSortedArrays(nums1, nums2):
        median = 0 
        num3 = list()
        for i in nums1:
            num3.append(i)
        for j in nums2:
            num3.append(j)
        num3.sort()
        length = len(num3) - 1
        middle = int(length/2)
        if len(num3) % 2 == 0:
            median = (num3[middle] + num3[middle+1])/2
        elif len(num3)%2==1:
            median = num3[middle]
        return float(median)
        
num1 = [1,2]
num2 = [3,4,5]
print(findMedianSortedArrays(num1,num2))