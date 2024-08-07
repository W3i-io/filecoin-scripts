SET ANSI_NULLS ON
GO

SET QUOTED_IDENTIFIER ON
GO

CREATE TABLE [dbo].[AccountsList](
	[ActorID] [nvarchar](16) NOT NULL,
	[Address] [nvarchar](128) NOT NULL,
	[Counter] [bigint] NOT NULL,
	[Active] [bit] NULL,
	[Description] [nvarchar](256) NULL,
	[IsMiner] [bit] NULL,
	[LastEpochCheckRewards] [bigint] NULL,
	[CheckAllMessages] [bit] NULL
) ON [PRIMARY]
GO


CREATE TABLE [dbo].[FilecoinTransactionsList](
	[RecordID] [bigint] IDENTITY(1,1) NOT NULL,
	[MessageID] [nvarchar](128) NOT NULL,
	[MessageDate] [datetime] NOT NULL,
	[ActorID] [nvarchar](16) NOT NULL,
	[Height] [bigint] NOT NULL,
	[Nonce] [bigint] NOT NULL,
	[MethodID] [int] NOT NULL,
	[MethodName] [nvarchar](50) NOT NULL,
	[ExitCode] [int] NOT NULL,
	[TransferType] [nvarchar](50) NOT NULL,
	[TransferFrom] [nvarchar](16) NOT NULL,
	[TransferTo] [nvarchar](16) NOT NULL,
	[TransferAmount] [numeric](38, 0) NOT NULL,
 CONSTRAINT [PK_FilecoinTransactionsList] PRIMARY KEY CLUSTERED 
(
	[RecordID] ASC
)WITH (STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
