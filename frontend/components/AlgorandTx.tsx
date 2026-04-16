type AlgorandTxProps = {
  txid: string;
  explorerUrl: string;
  confirmedRound?: number;
};

export function AlgorandTx({ txid, explorerUrl, confirmedRound }: AlgorandTxProps) {
  return (
    <div className="card p-5">
      <p className="kicker">Transaction</p>
      <p className="mono mt-2 break-all text-sm text-text">{txid}</p>
      {confirmedRound ? (
        <p className="mono mt-2 text-xs text-text-muted">confirmed round: {confirmedRound}</p>
      ) : null}
      <a
        className="mono mt-3 inline-block text-xs text-text-secondary underline underline-offset-2 hover:text-text transition-colors"
        href={explorerUrl}
        target="_blank"
        rel="noreferrer"
      >
        View on TestNet Explorer &rarr;
      </a>
    </div>
  );
}
