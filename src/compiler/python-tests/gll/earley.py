#implement early parser from page 6 of Derivation representation using binary subtree sets
#also implement conversion from BSR to SPPF
#test how fast it is compared to FUN-GLL parser
#also compare how complicated the implementation is
#once pick earley or fun-gll, last step is to figure out how to apply disambiguation filters, and any speedups from practical gll parsing


"""
Predictor((X ::= α · Y β, i), j)
{
    for all productions Y ::= γ
    {
        if(Y ::= ·γ, j) ∈ Sj
        {
            add (Y ::= ·γ, j) to Sj and to Rj 
        }
        for all (Y ::= δ·, j) ∈ Sj 
        {
            if(X ::= αY · β, j) ∈ Sj 
            {
                add (X ::= αY · β, j) to Sj and to Rj
                bsrAdd(X ::= αY · β, i, j, j) 
            } 
        } 
    }
}

Completer((X ::= α·, i), j){
    for all (Y ::= δ · Xμ, k) ∈ Si {
        if(Y ::= δX · μ, k) ∈ Sj {
            add (Y ::= δX · μ, k) to Sj and to Rj
            bsrAdd(X ::= α·, i, k, j) } }
}

Scanner((X ::= α · bβ, i), j){
    if(X ::= αb · β, i) ∈ Sj+1 {
        add (X ::= αb · β, i) to Sj+1 and to Rj+1
        bsrAdd(X ::= αb · β, i, j, j + 1) }
}

bsrAdd((X ::= α · β, i, k, j) {
    if(β = ){ insert (X ::= α, i, k, j) into Υ }
    else if(|α| > 1){ insert (α, i, k, j) into Υ }}
"""