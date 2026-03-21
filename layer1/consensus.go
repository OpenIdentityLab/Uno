package main

import "fmt"

// Vote represents a verifier vote for a candidate hash.
type Vote struct {
	Round    uint64
	VoterID  string
	BlockHash string
}

// QuorumCertificate is built when prepare reaches threshold.
type QuorumCertificate struct {
	Round     uint64
	BlockHash string
	Signers   []string
}

// HotStuffLite keeps 2-phase consensus state.
type HotStuffLite struct {
	PrepareVotes map[string]map[string]bool // blockHash -> voter -> true
}

func NewHotStuffLite() *HotStuffLite {
	return &HotStuffLite{PrepareVotes: make(map[string]map[string]bool)}
}

// Prepare records a vote and returns a QC when threshold is reached.
func (h *HotStuffLite) Prepare(v Vote, totalVerifiers int) (*QuorumCertificate, bool) {
	if _, ok := h.PrepareVotes[v.BlockHash]; !ok {
		h.PrepareVotes[v.BlockHash] = make(map[string]bool)
	}
	h.PrepareVotes[v.BlockHash][v.VoterID] = true
	count := len(h.PrepareVotes[v.BlockHash])
	if count >= quorumThreshold(totalVerifiers) {
		signers := make([]string, 0, count)
		for s := range h.PrepareVotes[v.BlockHash] {
			signers = append(signers, s)
		}
		return &QuorumCertificate{Round: v.Round, BlockHash: v.BlockHash, Signers: signers}, true
	}
	return nil, false
}

// Commit returns true when QC is valid for commit.
func (h *HotStuffLite) Commit(qc *QuorumCertificate, totalVerifiers int) bool {
	if qc == nil {
		return false
	}
	return len(qc.Signers) >= quorumThreshold(totalVerifiers)
}

func quorumThreshold(n int) int {
	if n <= 0 {
		return 1
	}
	return (2*n)/3 + 1
}

func phaseName(phase int) string {
	switch phase {
	case 0:
		return "PREPARE"
	case 1:
		return "COMMIT"
	default:
		return fmt.Sprintf("UNKNOWN(%d)", phase)
	}
}
