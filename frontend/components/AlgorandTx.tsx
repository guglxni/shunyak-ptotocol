type AlgorandTxProps = {
  txid: string;
  explorerUrl: string;
  confirmedRound?: number;
};

export function AlgorandTx({ txid, explorerUrl, confirmedRound }: AlgorandTxProps) {
  return (
    <div className="panel p-4">
      <p className="kicker">Algorand Transaction</p>
      <p className="mono mt-2 break-all text-sm text-paper">{txid}</p>
      {confirmedRound ? (
        <p className="mono mt-2 text-xs text-fog">confirmed round: {confirmedRound}</p>
      ) : null}
      <a
        className="mono mt-4 inline-block text-sm text-ocean underline"
        href={explorerUrl}
        target="_blank"
        rel="noreferrer"
      >
        View on Testnet Explorer
      </a>
    </div>
  );
}
