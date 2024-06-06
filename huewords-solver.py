"""CP model for solving the game Huewords."""


import sys

from ortools.sat.python import cp_model


def to_int(c):
    # A=0, B=1, ...
    return ord(c) - 65


def to_char(i):
    # 0=A, 1=B, ...
    return chr(i + 65)


# Load the word list
with open("words.txt", "r", encoding="utf-8") as f:
    words = [word.strip("\n").upper() for word in f.readlines()]

# Extract the information from the input file
with open(sys.argv[1], "r", encoding="utf-8") as f:
    lines = [line.strip("\n").upper() for line in f.readlines()]

given = lines[0]  # Word given initially
board = []        # Board template
lgroups = []      # Letter groups

# Parse the board and the letter groups
for line in lines[1:]:
    if any(c.isdigit() for c in line) or any(c == "." for c in line):
        board.append(line)
    elif any(c.isalpha() for c in line):
        lgroups.append(line)

num_rows = len(board)
num_cols = len(board[0])

# `bgroups` is a list of lists of coordinates representing cells in the same group
bgroups = {}

for row in range(num_rows):
    for col in range(num_cols):
        group = board[row][col]

        # Ignore empty cells
        if group == ".":
            continue

        # Put the coordinates of the same groups together
        if group in bgroups:
            bgroups[group].append((row, col))
        else:
            bgroups[group] = [(row, col)]

bgroups = list(bgroups.values())

# CP model
model = cp_model.CpModel()

# Convert letters to numbers
given = [to_int(c) for c in given]
lgroups = [[to_int(c) for c in lg] for lg in lgroups]
words = [[to_int(c) for c in word] for word in words]

# `letters[l][r][c]` indicates if letter `l` is found at coordinates `(r, c)`
letters = [[[None for col in range(num_cols)]
            for row in range(num_rows)]
           for _ in range(26)]

# `int_letters[r][c]` indicates which letter is found at coordinates `(r, c)`
int_letters = [[None for col in range(num_cols)]
               for row in range(num_rows)]

# There can only be letters in colored cells
for bg in bgroups:
    for c in bg:
        int_letters[c[0]][c[1]] = model.NewIntVar(0, 25, f"int_letters_{c[0]}_{c[1]}")
        for l in range(26):
            letters[l][c[0]][c[1]] = model.NewBoolVar(f"letters_{l}_{c[0]}_{c[1]}")

            # Link `letters` and `int_letters`
            model.Add(int_letters[c[0]][c[1]] == l).OnlyEnforceIf(letters[l][c[0]][c[1]])
            model.Add(int_letters[c[0]][c[1]] != l).OnlyEnforceIf(letters[l][c[0]][c[1]].Not())

# There can only be one letter per cell
for bg in bgroups:
    for c in bg:
        model.Add(cp_model.LinearExpr.Sum([letters[l][c[0]][c[1]] for l in range(26)]) == 1)

# Some letters cannot be assigned to some cells, because they don't appear in the letter groups of
# that size
lg_sets = {3: set(),
           4: set()}

for lg in lgroups:
    lg_sets[len(lg)] = lg_sets[len(lg)].union(set(lg))

for bg in bgroups:
    for c in bg:
        for l in range(26):
            if l not in lg_sets[len(bg)]:
                model.Add(letters[l][c[0]][c[1]] == 0)

# `lbg[lg][bg]` indicates if letter group `lg` is assigned to board group `bg`
lbg = [[model.NewBoolVar(f"lbg_{lg}_{bg}")
        for bg in range(len(bgroups))]
       for lg in range(len(lgroups))]

# Letter groups and board groups can only be assigned together if they are the same size
for lg in range(len(lgroups)):
    for bg in range(len(bgroups)):
        if len(lgroups[lg]) != len(bgroups[bg]):
            model.Add(lbg[lg][bg] == 0)

# A letter group can only be assigned to a single board group
for lg in range(len(lgroups)):
    model.Add(cp_model.LinearExpr.Sum([lbg[lg][bg] for bg in range(len(bgroups))]) == 1)

# A board group can only be assigned to a single letter group
for bg in range(len(bgroups)):
    model.Add(cp_model.LinearExpr.Sum([lbg[lg][bg] for lg in range(len(lgroups))]) == 1)

# If a letter group is assigned to a board group, this board group must use all letters from the
# associated letter group
for lg in range(len(lgroups)):
    for bg in range(len(bgroups)):
        if len(lgroups[lg]) == len(bgroups[bg]):
            for l in set(lgroups[lg]):
                model.Add(cp_model.LinearExpr.Sum([letters[l][c[0]][c[1]]
                                                   for c in bgroups[bg]])
                          == lgroups[lg].count(l)).OnlyEnforceIf(lbg[lg][bg])

# Prune the list of words to only include feasible words
words = [word for word in words if all(c in lg_sets[3].union(lg_sets[4]) for c in word)]

# Find all 5-letter word positions
word_positions = []

for row in range(num_rows):
    for i in range(len(board[row]) - 4):
        if all(j.isdigit() for j in board[row][i:i+5]):
            word_positions.append([(row, j) for j in range(i, i+5)])

for col in range(num_cols):
    for i in range(len(board) - 4):
        if all(j.isdigit() for j in [board[row][col] for row in range(i, i+5)]):
            word_positions.append([(j, col) for j in range(i, i+5)])

# Make sure all words on the board are in the word list
for wp in word_positions:
    model.AddAllowedAssignments([int_letters[c[0]][c[1]] for c in wp], words)

# `given_at[i]` indicates if the given word is placed in the `i`-th board group
given_at = [model.NewBoolVar(f"given_at_{i}") for i in range(len(bgroups))]

# Link `given_at` with `letters`
for i, wp in enumerate(word_positions):
    model.Add(cp_model.LinearExpr.Sum([letters[given[j]][wp[j][0]][wp[j][1]] for j in range(5)]) == 5).OnlyEnforceIf(given_at[i])

# The given word must appear
model.Add(cp_model.LinearExpr.Sum(given_at) >= 1)

# Solve the model
solver = cp_model.CpSolver()
solver.Solve(model)

# Print the solution
for row in range(num_rows):
    for col in range(num_cols):
        if int_letters[row][col] is None:
            print(" ", end="")
            continue
        print(to_char(solver.Value(int_letters[row][col])), end="")
    print()
