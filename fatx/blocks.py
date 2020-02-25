#!/bin/env python3
import struct
import enum

SUPERBLOCK_SIZE = 4096
SECTOR_SIZE = 512
DIRECTORY_SIZE = 64

class SuperBlock():
	"""
	Offset	Size	Description
	0		4		"FATX" string (ASCII)
	4		4		Volume ID (int)
	8		4		Cluster size in (512 byte) sectors
	12		2		Number of FAT copies
	14		4		Unknown (always 0?)
	18		4078	Unused
	"""
	SUPERBLOCK_SIZE = 4096
	SECTOR_SIZE = 512
	SB_OFS_Name = 0
	SB_SIZE_Name = 4
	SB_OFS_VolumeId = 4
	SB_SIZE_VolumeId = 4
	SB_OFS_ClusterSize = 8
	SB_SIZE_ClusterSize = 4
	SB_OFS_FATCopies = 12
	SB_SIZE_FATCopies = 2
	SB_OFS_Unkown = 14
	SB_SIZE_Unkown = 4
	SB_OFS_Unused = 18
	SB_SIZE_Unused = 4078

	def __init__(self, sb):
		if(SUPERBLOCK_SIZE != len(sb)):
			print('SuperBlock is not '+ str(SUPERBLOCK_SIZE) +' bytes long')
			raise BaseException
		self.name, self.volume, self.clusternum, self.fatcopies = struct.unpack('4sIIh4082x',sb)
		self.name = self.name.decode("ascii") 
		assert("FATX" == self.name)
		assert(1 == self.fatcopies)
		assert(32 == self.clusternum)

	def clusterSize(self):
		return self.clusternum * SECTOR_SIZE

	def __str__(self):
		return self.name


class EntryType(enum.Enum):
	FATX_CLUSTER_AVAILABLE = 0
	FATX_CLUSTER_RESERVED = 1
	FATX_CLUSTER_BAD = 2
	FATX_CLUSTER_DATA = 3
	FATX_CLUSTER_END = 4


class FAT():
	"""
	| 	0x0000		| This cluster is free for use 
	| 	0x0001		| Usually used for recovery after crashes(unkown if used by the xbox) 
	|0x0002 - 0xFFEF| This cluster is part of a chain and points to the next cluster 
	|0xFFF0 - 0xFFF5| Reserved(unkown if used by the xbox) 
	| 	0xfff7		| Bad sectors in this cluster - this cluster should not be used 
	|0xfff8 - 0xffff| Marks the end of a cluster chain 
	"""

	def __init__(self, raw_clustermap, clustersize):
		self.f = raw_clustermap
		self.size = clustersize
		self.clustermap = []

		# slice up the fat table
		while len(self.f) > 0:
			entry = int.from_bytes(self.f[:self.size], 'little')
			self.f = self.f[self.size:]
			self.clustermap.append(entry)

	def numberClusters(self):
		return len(self.clustermap)

	def getEntryType(self, entry):
		if entry == 0x0000:
			return EntryType.FATX_CLUSTER_AVAILABLE
		if entry == 0x0001:
			return EntryType.FATX_CLUSTER_RESERVED
		if self.size == 2:
			if entry == 0xFFF7:
				return EntryType.FATX_CLUSTER_BAD
			if entry > 0xFFF7:
				return EntryType.FATX_CLUSTER_END
		else:
			if entry == 0xFFFFFFF7:
				return EntryType.FATX_CLUSTER_BAD
			if entry > 0xFFFFFFF7:
				return EntryType.FATX_CLUSTER_END
		return EntryType.FATX_CLUSTER_DATA

	# collects the IDs/No. of clusters of a chain of a given start cluster 
	def clusterChain(self, pointer):
		l = []
		l.append(pointer)

		# Your first pointer should always point to either the next 
		# clusterchain element or mark the end of a chain
		nvalue = self.getEntryType(self.clustermap[pointer])
		if nvalue not in [EntryType.FATX_CLUSTER_DATA, EntryType.FATX_CLUSTER_END]:
			raise ValueError("Start cluster is not part of a chain")

		# We are not at the end of the chain
		while nvalue != EntryType.FATX_CLUSTER_END:
			# get the next pointer
			pointer = self.clustermap[pointer]
			l.append(pointer)
			# lookup the pointer, so we can check if it is the end of the chain
			nvalue = self.getEntryType(self.clustermap[pointer])
			if nvalue in [EntryType.FATX_CLUSTER_BAD, EntryType.FATX_CLUSTER_RESERVED, EntryType.FATX_CLUSTER_AVAILABLE]:
				raise ValueError("One chain element is invalid", nvalue)
		return l

	def __str__(self):
		return str(self.numberClusters()) + ' Clusters in map'


class DirectoryEntry():
	""" 
	DirectoryEntry, byte representation
	Offset	Size	Description
	0		1		Size of filename (max. 42)
	1		1		Attribute as on FAT
	2		42		Filename in ASCII, padded with 0xff (not zero-terminated)
	44		4		First cluster
	48		4		File size in bytes
	52		2		Modification time
	54		2		Modification date
	56		2		Creation time
	58		2		Creation date
	60		2		Last access time
	62		2		Last access date
	"""
	DIRECTORY_SIZE = 64
	D_OFS_NAMESIZE = 0
	D_SIZE_NAMESIZE = 1
	D_OFS_ATTRIBUT = 1
	D_SIZE_ATTRIBUT = 1
	D_OFS_NAME = 2
	D_SIZE_NAME = 42
	D_OFS_CLUSTER = 44
	D_SIZE_CLUSTER = 4
	D_OFS_FILESIZE = 48
	D_SIZE_FILESIZE = 4

	"""
	Attributes, byte values/mask
	0x01 - Indicates that the file is read only.
	0x02 - Indicates a hidden file. Such files can be displayed if it is really required.
	0x04 - Indicates a system file. These are hidden as well.
	0x08 - Indicates a special entry containing the disk's volume label, instead of describing a file. This kind of entry appears only in the root directory.
	0x10 - The entry describes a subdirectory.
	0x20 - This is the archive flag. This can be set and cleared by the programmer or user, but is always set when the file is modified. It is used by backup programs.
	0x40 - Not used; must be set to 0.
	0x80 - Not used; must be set to 0.
	"""
	ATR_READONLY = 0x01
	ATR_HIDDEN = 0x02
	ATR_SYSTEM = 0x04
	ATR_VOLUMELABEL = 0x08
	ATR_DIRECTORY = 0x10
	ATR_ARCHIVE = 0x20

	class Attributes():
		READONLY = False
		HIDDEN = False
		SYSTEM = False
		VOLUMELABEL = False
		DIRECTORY = False
		ARCHIVE = False
		DELETED = False


	def __init__(self, d):
		self.atr = self.Attributes()
		if(DIRECTORY_SIZE != len(d)):
			print('Directory is '+str(len(d))+' bytes long. Expected '+ str(self.DIRECTORY_SIZE) +' bytes.')
			raise ValueError('Directory is '+str(len(d))+' bytes long. Expected '+ str(self.DIRECTORY_SIZE) +' bytes.')
		raw = struct.unpack('BB42sII12x',d)
		self.namesize = raw[0]

		# This is not a real entry, it marks the end of the list
		if 0xFF == self.namesize or 0x00 == self.namesize:
			raise StopIteration("Reached end of DirectoryEntry list")

		if 0xE5 == self.namesize:
			self.atr.DELETED = True
			self.namesize = 42

		# The size of a name cannot exceed the actual byte length of the name field
		if(42 < self.namesize):
			raise SystemError("Namesize is longer("+hex(self.namesize)+")then max length("+hex(42)+")")

		self.attributes = raw[1]

		self.name = raw[2]
		self.cluster = raw[3] # first cluster of the file
		self.size = raw[4]

		self.atr.READONLY = bool(self.attributes & self.ATR_READONLY)
		self.atr.HIDDEN = bool(self.attributes & self.ATR_HIDDEN)
		self.atr.SYSTEM = bool(self.attributes & self.ATR_SYSTEM)
		self.atr.VOLUMELABEL = bool(self.attributes & self.ATR_VOLUMELABEL)
		self.atr.DIRECTORY = bool(self.attributes & self.ATR_DIRECTORY)
		self.atr.ARCHIVE = bool(self.attributes & self.ATR_ARCHIVE)
		self.filename = "".join([chr(i) for i in self.name[:self.namesize] if i > 0x1F and i < 0x7F])

	def __str__(self):
		return self.filename
