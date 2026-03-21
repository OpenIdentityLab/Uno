package main

import (
	"crypto/sha256"
	"encoding/hex"
	"sort"
	"strconv"
)

// RoundState tracks VRF selection and voting for one round.
type RoundState struct {
	Number    uint64
	Seed      string
	Producers []string
	Verifiers []string
	Votes     map[string][]Vote // blockHash -> votes
	Finalized bool
}

func NewRoundState(number uint64, prevBlockHash string) *RoundState {
	h := sha256.Sum256([]byte(prevBlockHash + ":" + strconv.FormatUint(number, 10)))
	return &RoundState{
		Number: number,
		Seed:   hex.EncodeToString(h[:]),
		Votes:  make(map[string][]Vote),
	}
}

// SelectValidators ranks nodes by VRF output and chooses producer/verifier sets.
func (r *RoundState) SelectValidators(nodes []string, producerCount, verifierCount int) error {
	type scored struct {
		id    string
		score string
	}
	scores := make([]scored, 0, len(nodes))
	for _, id := range nodes {
		out, _, err := ComputeVRF(r.Seed, id)
		if err != nil {
			return err
		}
		scores = append(scores, scored{id: id, score: out})
	}

	sort.Slice(scores, func(i, j int) bool {
		return scores[i].score < scores[j].score
	})

	if producerCount > len(scores) {
		producerCount = len(scores)
	}
	r.Producers = r.Producers[:0]
	for i := 0; i < producerCount; i++ {
		r.Producers = append(r.Producers, scores[i].id)
	}

	start := producerCount
	if start > len(scores) {
		start = len(scores)
	}
	end := start + verifierCount
	if end > len(scores) {
		end = len(scores)
	}
	r.Verifiers = r.Verifiers[:0]
	for i := start; i < end; i++ {
		r.Verifiers = append(r.Verifiers, scores[i].id)
	}
	return nil
}

func (r *RoundState) AddVote(v Vote) {
	r.Votes[v.BlockHash] = append(r.Votes[v.BlockHash], v)
}

func (r *RoundState) IsFinalized(blockHash string) bool {
	count := len(r.Votes[blockHash])
	ok := count >= quorumThreshold(len(r.Verifiers))
	if ok {
		r.Finalized = true
	}
	return ok
}
