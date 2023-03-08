import pandas as pd
import numpy as np

from torch.utils.data import Dataset

def prepare_for_analysis(filename):
	data_array = pd.read_csv(filename,header=None).values

	# -- Removes the columns with all -9 values -- 
	row_no = 0 
	for row in data_array:
		for col_i in range(1,row.shape[0]):
			if (row[col_i] == -9):
				remove = True
			else:
				remove = False
				break

		if remove:
			data_array = np.delete(data_array, row_no, 0)

		else:
			row_no += 1

	return data_array

class MyDataset(Dataset):
    def __init__(self,data):
        self.data=data
    def __getitem__(self,index):
        return self.data['X'][index],self.data['Y'][index]
    def __len__(self):
        return len(self.data["X"])