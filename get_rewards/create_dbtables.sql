SET ANSI_NULLS ON
GO

SET QUOTED_IDENTIFIER ON
GO

CREATE TABLE [dbo].[BlockRewards](
	[RewardDate] [datetime] NOT NULL,
	[BlockReward] [decimal](18, 16) NOT NULL
) ON [PRIMARY]
GO

