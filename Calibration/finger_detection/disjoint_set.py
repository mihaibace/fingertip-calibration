'''
(*)~---------------------------------------------------------------------------
Copyright (C) 2017-2018  Sander Staal
---------------------------------------------------------------------------~(*)
'''

class DisjointSet:

	disjoint_set = list()
	set_member_lookup = {}

	def __init__(self, init_arr):
		self.disjoint_set = []
		self.set_member_lookup = {}

		if init_arr:
			for index, item in enumerate(set(init_arr)):
				self.disjoint_set.append([item])
				self.set_member_lookup[item] = index

	def find(self, elem):
		if elem in self.set_member_lookup:
			return self.set_member_lookup[elem]
		else:
			return None
	
	def union(self, elem1, elem2):
		index_elem1 = self.find(elem1)
		index_elem2 = self.find(elem2)

		if self.disjoint_set[index_elem1] is None or self.disjoint_set[index_elem2] is None:
			return self.disjoint_set

		if index_elem1 is None or index_elem2 is None:
			return self.disjoint_set

		if index_elem1 != index_elem2:
			self.disjoint_set[index_elem2].extend(list(self.disjoint_set[index_elem1]))
			
			for k in self.disjoint_set[index_elem1]:
				self.set_member_lookup[k] = index_elem2

			self.disjoint_set[index_elem1] = None

		return self.disjoint_set	

	def get(self):
		return [e for e in self.disjoint_set if e is not None]
	

