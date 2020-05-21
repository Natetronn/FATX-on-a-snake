import io, os, math
from .blocks import SuperBlock, FAT, DirectoryEntry, DirectoryEntryList
from .interface2 import *

"""
This file mainly contains horrible code. Please don't look to much at it. 
It links the high abstraction (public) API form interface.py with 
the byte-representing objects in blocks.py. 
It should be the only place where data is read and written. 
"""

READ_ONLY = True

SUPERBLOCK_SIZE = 4096
SECTOR_SIZE = 512
DIRECTORY_SIZE = 64

FATX16 = 2
FATX32 = 4

def writingWarning(func):
	def call(*args, **kwargs):
		print("Warning! Writing changes to the disk!")
		if not READ_ONLY:
			return func(*args, **kwargs)
		else:
			raise SystemError("User abort, change READ_ONLY to False")

	return call

class Filesystem():
	def __init__(self, file):
		self.f = open(file, 'r+b')
		self.sb = SuperBlock(self.f.read(SUPERBLOCK_SIZE))

		self.fat_size = self._calc_fat_size(os.stat(file).st_size, self.sb.clustersize)
		self.fat = FAT(self.f.read(self.fat_size))

		# Sadly, sometimes the interfaces need to access the filesystem
		FatxObject.registerFilesystem(self)

		# Read the first(yes, 1, not zero) Cluster, it should contain the root DirectoryEntry list
		cluster = self._get_cluster(1)
		self.root = RootObject(DirectoryEntryList(cluster, 1))

	# returns a DirectoryEntryList from the cluster assosiated in the given directoryentry
	def open_directory(self, de: DirectoryEntry):
		assert(de.atr.DIRECTORY)
		cluster = self._get_cluster(de.cluster)
		try:
			return DirectoryEntryList(cluster, de.cluster)
		except SystemError as e:
			print(e)
			self._print_debug(de)
			return None

	# Reads a File and returns it
	def read_file(self, de: DirectoryEntry):
		data = bytearray()
		if de.atr.DIRECTORY:
			raise ValueError("This is a directory, not a file")
		try:
			clusters = self.fat.clusterChain(de.cluster)
			for i in clusters:
				data += self._get_cluster(i)
			return data[:de.size]
		except Exception as e:
			print(e)
			self._print_debug(de)
			print("\tread {0} from {1} bytes".format(len(data), de.size))
			return data

	def status(self):
		print(self.__str__())

	def _get_cluster(self, ID: int):
		self.f.seek(self._cluster_id_offset(ID))
		return self.f.read(self.sb.clustersize)

	# Calculates the offset for a given clusterID
	def _cluster_id_offset(self, ID: int):
		if ID == 0:
			raise ValueError("Cluster ID must be greater then 0")
		#(Number of your cluster -1) * cluster size + Superblock + FAT
		return (ID-1) * self.sb.clustersize + SUPERBLOCK_SIZE + self.fat_size

	@staticmethod
	def _calc_fat_size(partition_size: int, cluster_size: int = 32*512):
		# ((partition size in bytes / cluster size) * cluster map entry size)
		# rounded up to nearest 4096 byte boundary.
		number_of_clusters = partition_size / cluster_size
		size = FATX16 if number_of_clusters <= 0xfff5 else FATX32 # deciding how big a fat entry is in bytes
		fat_size = number_of_clusters * size
		if fat_size % 4096:
			fat_size += 4096 - fat_size % 4096
		return int(fat_size)

	def _print_debug(self, de: DirectoryEntry):
		print("\tName: {0}".format(de.filename))
		print("\tCluster ID: {0}".format(de.cluster))
		try:
			print("\tOffset: 0x{0:X}".format(self._cluster_id_offset(de.cluster)))
		except:
			print("\tOffset: Failed calculating the offset")

	def __str__(self):
		return "{0} ~ {1}".format(str(self.sb), str(self.fat))

