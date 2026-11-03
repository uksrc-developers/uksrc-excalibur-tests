#!/bin/bash
#SBATCH --job-name test_pspec
#SBATCH --nodes 1
#SBATCH --ntasks-per-node 54
#SBATCH --cpus-per-task 1
#SBATCH --time 59-00:00:00
#SBATCH --mem 160GB
#SBATCH --output ./slurm-out/%J.out

source ~/.bashrc

echo "start: $(date)"
apptainer run $@
echo "end: $(date)"
