from __future__  import division
from collections import defaultdict
from nltk.align  import AlignedSent
from nltk.align  import Alignment
from nltk.corpus import comtrans
from ibm_model_2 import IBMModel2
from math import factorial

class hashabledict(dict):
    """
    This class implements a hashable dict, which can be 
    put into a set.
    """
    def __key(self):
        return tuple((k,self[k]) for k in sorted(self))

    def __hash__(self):
        return hash(self.__key())

    def __eq__(self, other):
        return self.__key() == other.__key()

class IBMModel3(object):
    """
    This class implements the algorithm of Expectation Maximization for 
    the IBM Model 3. 

    Step 1 - Run a number of iterations of IBM Model 2 and get the initial
             distribution of translation probability. 

    Step 2 - Sample the alignment spaces by using the hillclimb approach. 

    Step 3 - Collect the evidence of translation probabilities, distortion, 
    		 the probability of null insertion, and fertility. 

    Step 4 - Estimate the new probabilities according to the evidence from 
             Step 3. 

    >>> alignSents = []
    >>> alignSents.append(AlignedSent(['klein', 'ist', 'das', 'Haus'], ['the', 'house', 'is', 'small']))
    >>> alignSents.append(AlignedSent(['das', 'Haus'], ['the', 'house'])) 
    >>> alignSents.append(AlignedSent(['das', 'Buch'], ['the', 'book']))
    >>> alignSents.append(AlignedSent(['ein', 'Buch'], ['a', 'book']))

    >>> ibm3 = IBMModel3(alignSents, 5)

    >>> print "%.1f" % ibm3.probabilities['Buch']['book']
    1.0
    >>> print "%.1f" % ibm3.probabilities['das']['book']
    0.0
    >>> print "%.1f" % ibm3.probabilities[None]['book']
    0.0

    >>> aligned_sent = ibm3.align(alignSents[0])
    >>> aligned_sent.words
    ['klein', 'ist', 'das', 'Haus']
    >>> aligned_sent.mots
    ['the', 'house', 'is', 'small']
    >>> aligned_sent.alignment
    Alignment([(0, 2), (1, 3), (2, 0), (3, 1)])

    """

    def __init__(self, alignSents, num_iter):
        # If there is not an initial value, it throws an exception of 
        # the number divided by zero. And the value of computing 
        # probability will be always zero.
        self.PROB_SMOOTH = 0.1

        self.train(alignSents, num_iter)


    def train(self, alignSents, num_iter):
        """
        This function is the main process of training model, which
        initialize all the probability distributions and executes 
        a specific number of iterations. 
        """
        # Get the translation and alignment probabilities from IBM model 2
        ibm2 = IBMModel2(alignSents, num_iter)
        self.probabilities, self.alignTable = ibm2.probabilities, ibm2.alignments

        fr_vocab = set()
        en_vocab = set()
        for alignSent in alignSents:
            en_vocab.update(alignSent.words)
            fr_vocab.update(alignSent.mots)
        fr_vocab.add(None)

        # Initial probability of null insertion.
        self.nullInsertion = 0.5 

        self.fertility = defaultdict(lambda: defaultdict(lambda: self.PROB_SMOOTH)) 
        self.distortion = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: self.PROB_SMOOTH))))

        for k in range(0, num_iter):
            maxFert = 0
            # Set all count* and total* to 0
            count_t = defaultdict(lambda: defaultdict(lambda: 0.0))
            total_t = defaultdict(lambda: 0.0)

            count_d = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: 0.0))))
            total_d = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: 0.0)))

            count_p0 = 0.0
            count_p1 = 0.0

            count_f = defaultdict(lambda: defaultdict(lambda: 0.0))
            total_f = defaultdict(lambda: 0.0)

            for alignSent in alignSents:

                en_set = alignSent.words
                fr_set = [None] + alignSent.mots
                l_f = len(fr_set) - 1
                l_e = len(en_set)

                # Sample the alignment space
                A = self.sample( en_set, fr_set)
                
                # Collect counts
                c_total = 0.0

                for (a, fert) in A:
                    c_total += self.probability(a, en_set, fr_set, fert)

                for (a, fert) in A:
                    c = self.probability(a, en_set, fr_set, fert)/c_total
                    null = 0

                    for j in range(1, l_e+1):
                        en_word = en_set[j-1]
                        fr_word = fr_set[a[j]]

                        # Lexical translation
                        count_t[en_word][fr_word] += c
                        total_t[fr_word] += c

                        # Distortion
                        count_d[j][a[j]][l_e][l_f] += c
                        total_d[a[j]][l_e][l_f] += c

                        if a[j] == 0:
                            null += 1

                    # Collect the counts of null insetion
                    count_p1 += null * c
                    count_p0 += (l_e - 2 * null) * c

                    # Collect the counts of fertility
                    for i in range(0, l_f+1):
                        fertility = 0

                        for j in range(1, l_e+1):
                            if i == a[j]:
                                fertility += 1

                        fr_word = fr_set[i]
                        count_f[fertility][fr_word] += c
                        total_f[fr_word] += c

                        if fertility > maxFert:
                            maxFert = fertility

			
            self.probabilities = defaultdict(lambda: defaultdict(lambda: 0.0))
            self.distortion = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: 0.0))))	
            self.fertility = defaultdict(lambda: defaultdict(lambda: 0.0))

            # Estimate translation probability distribution
            for f in fr_vocab:
                for e in en_vocab:
                    self.probabilities[e][f] = count_t[e][f] / total_t[f]

            # Estimate distortion
            for alignSent in alignSents:
                en_set = alignSent.words
                fr_set = [None] + alignSent.mots
                l_f = len(fr_set) - 1
                l_e = len(en_set)

                for i in range(0, l_f+1):
                    for j in range(1, l_e+1):
                        self.distortion[j][i][l_e][l_f] = count_d[j][i][l_e][l_f] / total_d[i][l_e][l_f]

            # Estimate the fertility, n(Fertility | input word)
            for ferti in range(0, maxFert+1):
                for fr_word in fr_vocab:
                    self.fertility[ferti][fr_word] = count_f[ferti][fr_word] / total_f[fr_word]

            # Estimate the probability of null insertion
            p1 = count_p1 / (count_p1+count_p0)
            self.nullInsertion = 1 - p1

    def sample(self, e, f):
        """
        This function returns a sample from the entire alignment space.
        First, it pegs one alignment point and finds out the best alignment
        through the IBM model 2. Then, using the hillclimb approach, it 
        finds out the best alignment on local and returns all its neighborings,
        which are swapped or moved one distance from the best alignment.
        """
        A = set()

        le = len(e)
        lf = len(f) - 1

        # Compute Normalization
        for i in range(0, lf+1):
            for j in range(1, le+1):
                a = hashabledict()
                Fert = hashabledict()
                # Initialize all fertility to zero
                for ii in range(0, lf+1):
                    Fert[ii] = 0

                # Pegging one alignment point
                a[j] = i
                Fert[i] = 1

                for jj in range(1, le+1):
                    if jj != j:
                        # Find the best alignment according to model 2
                        maxalignment = 0
                        besti = 1

                        for ii in range(0, lf+1): 
                            # Notice that the probabilities returned by IBM model 2, 
                            # which is not distortion, is alignment. 
                            #
                            # The alignment probability predicts foreign input word
                            # positions conditioned on English output word positions.
                            # However, the distortion probability in a reverse direction
                            # predicts the output word position based on input word 
                            # position. 
                            # 
                            # Actually, you cannot just change the index to get a 
                            # distortion from alignment table, because its process of 
                            # collecting evidence is different from each other.
                            alignment = self.probabilities[e[jj-1]][f[ii]] * self.alignTable[ii][jj][le][lf]
                            if alignment > maxalignment:
                                maxalignment = alignment
                                besti = ii

                        a[jj] = besti
                        Fert[besti] += 1

                a = self.hillclimb(a, j, e, f, Fert)
                neighbor = self.neighboring(a, j, e, f, Fert)
                A.update(neighbor)

        return A

    def hillclimb(self, a, j_pegged, es, fs, Fert):
        """
        This function returns the best alignment on local. It gets 
        some neighboring alignments and finds out the alignment with 
        highest probability in those alignment spaces. If the current
        alignment recorded has the highest probability, then stop the
        search loop. If not, then continue the search loop until it 
        finds out the highest probability of alignment in local.
        """
        so_far_Fert = Fert

        while True:
            a_old = a

            for (a_nerghbor, neighbor_Fert) in self.neighboring(a, j_pegged, es, fs, so_far_Fert):
                if self.probability(a_nerghbor, es, fs, neighbor_Fert) > self.probability(a, es, fs, so_far_Fert):
                    # If the probability of an alignment is higher than 
                    # the current alignment recorded, then replace the 
                    # current one. 
                    a = a_nerghbor
                    so_far_Fert = neighbor_Fert

            if a == a_old:
                # Until this alignment is the highest one in local
                break

        return a

    def probability(self, a, es, fs, Fert):
        """
        This function returns the probability given an alignment. 
        The Fert variable is math syntax 'Phi' in the fomula, which 
        represents the fertility according to the current alignment,
        which records how many output words are generated by each 
        input word.
        """
        l_e = len(es)
        l_f = len(fs) - 1
        p1 = 1 - self.nullInsertion

        total = 1.0

        # Compute the NULL insertation
        total *= pow(p1, Fert[0]) * pow(self.nullInsertion, l_e - 2 * Fert[0])
        if total == 0:
            return total

        # Compute the combination (l_e - Fert[0]) choose Fert[0]
        for i in range(1, Fert[0]+1):
            total *= (l_e - Fert[0] - i + 1) / i
            if total == 0:
                return total

        # Compute fertilities term
        for i in range(1, l_f+1):
            total *= factorial(Fert[i]) * self.fertility[Fert[i]][fs[i]]
            if total == 0:
                return total

        # Multiply the lexical and distortion probabilities
        for j in range(1, l_e+1):
            en_word = es[j-1]
            fr_word = fs[a[j]]

            total *= self.probabilities[en_word][fr_word]
            total *= self.distortion[j][a[j]][l_e][l_f]
            if total == 0:
                return total

        return total

    def neighboring(self, a, j_pegged, es, fs, Fert):
        """
        This function returns the neighboring alignments from
        the given alignment by moving or swapping one distance.
        """
        N = set()

        l_e = len(es)
        l_f = len(fs) - 1

        for j in range(1, l_e+1):
            if j != j_pegged:
                # Moves
                for i in range(0, l_f+1):
                    new_align = hashabledict(a)
                    new_align[j] = i

                    new_Fert = Fert
                    if new_Fert[a[j]] > 0:
                    	new_Fert = hashabledict(Fert)
                        new_Fert[a[j]] -= 1
                        new_Fert[i] += 1

                    N.update([(new_align, new_Fert)])


        for j_one in range(1, l_e+1):
            if j_one != j_pegged:
                # Swaps
                for j_two in range(1, l_e+1):
                    if j_two != j_pegged and j_two != j_one:
                        new_align = hashabledict(a)
                        new_Fert = Fert
                        new_align[j_one] = a[j_two]
                        new_align[j_two] = a[j_one]

                        N.update([(new_align, new_Fert)])

        return N

    def align(self, alignSent):
        """
        Returns the alignment result for one sentence pair. 
        """

        if self.probabilities is None or self.distortion is None:
            raise ValueError("The model does not train.")

        alignment = []

        l_e = len(alignSent.words);
        l_f = len(alignSent.mots);

        for j, en_word in enumerate(alignSent.words):
            
            # Initialize the maximum probability with Null token
            max_alignProb = (self.probabilities[en_word][None]*self.distortion[j+1][0][l_e][l_f], None)
            for i, fr_word in enumerate(alignSent.mots):
                # Find out the maximum probability
                max_alignProb = max(max_alignProb,
                    (self.probabilities[en_word][fr_word]*self.distortion[j+1][i+1][l_e][l_f], i))

            # If the maximum probability is not Null token,
            # then append it to the alignment. 
            if max_alignProb[1] is not None:
                alignment.append((j, max_alignProb[1]))

        return AlignedSent(alignSent.words, alignSent.mots, alignment)

# run doctests
if __name__ == "__main__":
    import doctest
    doctest.testmod()
